#!/usr/bin/python3

# Copyright 2019 Peter Green
# Released under the MIT/Expat license,

import urllib.request
import lzma
import subprocess
import yaml
import sys
import argparse
from collections import defaultdict
from debian import deb822

archlist = ['amd64','arm64', 'armel','armhf','i386','mips','mips64el','mipsel','ppc64el','s390x']
archset = set(archlist)
dist = 'buster'
baseurl = 'https://mirror.bytemark.co.uk/debian'

parser = argparse.ArgumentParser(description="checks debian for self-contained buildability problems")
parser.add_argument("--nodownload", help="skip download step, use existing downloaded files", action="store_true")
parser.add_argument("--nodose", help="skip first dose step, use existing dose output files", action="store_true")
args = parser.parse_args()

def downloadanddecompress(fileurl,outputpath):
	with urllib.request.urlopen(fileurl) as response:
		rdc = lzma.open(response)
		data = rdc.read()
	f = open(outputpath,'wb')
	f.write(data)
	f.close()

url = baseurl+'/dists/'+dist+'/main/source/Sources.xz'
path = 'neededsources'
if not args.nodownload:
	print('downloading '+url)
	downloadanddecompress(url,path)

failures = defaultdict(dict)
neededsources = defaultdict(set)
for arch in archlist:
	url = baseurl+'/dists/'+dist+'/main/binary-'+arch+'/Packages.xz'
	path = arch+'-Packages'
	if not args.nodownload:
		print('downloading '+url)
		downloadanddecompress(url,path)
	if not args.nodose:
		command = ['dose-builddebcheck','--deb-native-arch='+arch,'-f','-o',arch+'-builddebcheck','--explain',path,'Sources']
		print("running: "+repr(command))
		result = subprocess.call(command)
		if result > 1:
			print('unrecognised exit code from dose-builddebcheck, aborting')
			sys.exit(1)
	f = open(arch+'-builddebcheck','r')
	dco = yaml.safe_load(f)
	dco = dco['report']
	for failure in dco:
		source = failure['package']
		reasons = failure['reasons']
		failures[source][arch] = reasons
	f.close()
	#print(repr(dco)[:80])
	#sys.exit(1)
	
	print('reading and parsing '+path)
	f = open(path,'r')
	for pkgentry in deb822.Packages.iter_paragraphs(f):
		if "Source" in pkgentry:
			source = pkgentry["Source"].split(" ")[0]
		else:
			source = pkgentry["Package"]
		neededsources[source].add(pkgentry['Architecture'])
	f.close()
	
	
	
	
	
#print(repr(neededsources))
indepbroken = set()
from collections import OrderedDict
furtherchecksources = OrderedDict()
for source, neededarches in sorted(neededsources.items()):
	#print(source)
	brokenarches = set(failures[source].keys())
	scbarches = neededarches & brokenarches
	if ("all" in neededarches) and (brokenarches == archset):
		scbarches.add("all")
		indepbroken.add(source)
	if scbarches != set():
		furtherchecksources[source] = neededarches

command = ['grep-dctrl','-P','-e','^('+'|'.join(furtherchecksources)+')$','Sources']
print("running: "+repr(command))
output = subprocess.check_output(command)
f = open('furtherchecksources','wb')
f.write(output)
f.close()

failures = defaultdict(dict)
for arch in archlist:
	path = arch+'-Packages'
	command = ['dose-builddebcheck','--deb-native-arch='+arch,'-f','-o',arch+'-builddebcheckao','--explain','--deb-drop-b-d-indep',path,'furtherchecksources']
	print("running: "+repr(command))
	result = subprocess.call(command)
	if result > 1:
		print('unrecognised exit code from dose-builddebcheck, aborting')
		sys.exit(1)
	f = open(arch+'-builddebcheckao','r')
	dco = yaml.safe_load(f)
	dco = dco['report']
	for failure in dco:
		source = failure['package']
		reasons = failure['reasons']
		failures[source][arch] = reasons
	f.close()
	#print(repr(dco)[:80])
	#sys.exit(1)
	

for source, neededarches in furtherchecksources.items():
	brokenarches = set(failures[source].keys())
	scbarches = neededarches & brokenarches
	if source in indepbroken:
		scbarches.add("all")
	if scbarches != set():
		print(source+': '+', '.join(sorted(scbarches)))
