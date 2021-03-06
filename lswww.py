#!/usr/bin/env python

# Powerfuzzer
# Copyright (C) 2008 Marcin Kozlowski
# Using lswww component by:
# lswww v2.1.5 - A web spider library
# Copyright (C) 2006 Nicolas Surribas
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import sys, re, socket, getopt, os
import HTMLParser,urllib,urllib2
import time

import  wx
import  wx.lib.newevent
import wx.richtext as rt


try:
	import cookielib
except ImportError:
	cookielibhere=0
else:
	cookielibhere=1

try:
	import tidy
except ImportError:
	print "lswww will be far less effective without tidy"
	print "please install libtidy ( http://tidy.sourceforge.net/ ),"
	print "ctypes ( http://starship.python.net/crew/theller/ctypes/ )"
	print "and uTidylib ( http://utidylib.berlios.de/ )"
	tidyhere=0
else:
	tidyhere=1

try:
	import BeautifulSoup
except ImportError:
	BeautifulSouphere=0
else:
	BeautifulSouphere=1

class lswww:
	"""
	lswww explore a website and extract links and forms fields.

Usage: python lswww.py http://server.com/base/url/ [options]

Supported options are:
-s <url>
--start <url>
	To specify an url to start with

-x <url>
--exclude <url>
	To exclude an url from the scan (for example logout scripts)
	You can also use a wildcard (*)
	Exemple : -x "http://server/base/?page=*&module=test"
	or -x http://server/base/admin/* to exclude a directory

-p <url_proxy>
--proxy <url_proxy>
	To specify a proxy
	Exemple: -p http://proxy:port/

-c <cookie_file>
--cookie <cookie_file>
	To use a cookie

-a <login%password>
--auth <login%password>
	Set credentials for HTTP authentication
	Doesn't work with Python 2.4

-r <parameter_name>
--remove <parameter_name>
	Remove a parameter from URLs

-v <level>
--verbose <level>
	Set verbosity level
	0: only print results
	1: print a dot for each url found (default)
	2: print each url

-t <timeout>
--timeout <timeout>
	Set the timeout (in seconds)

-h
--help
	To print this usage message
	"""

	root=""
	server=""
	tobrowse=[]
	browsed=[]
	proxy={}
	excluded=[]
	forms=[]
	uploads=[]
	allowed=['php','html','htm','xml','xhtml','xht','xhtm',
	         'asp','aspx','php3','php4','php5','txt','shtm',
		 'shtml','phtm','phtml','jhtml','pl','jsp','cfm','cfml']
	verbose=2
	cookie=""
	auth_basic=[]
	bad_params=[]
	timeout=6
	box=""

	def __init__(self,rooturl,box,timeToQuit):
		root=rooturl
	        self.box=box
		self.timeToQuit=timeToQuit
		if root[-1]!="/":
			root+="/"
		if(self.checklink(root)):
			#print "Invalid link argument"
			wx.CallAfter(self.write_to_box,"Invalid URI: "+root)
			self.timeToQuit.set()
			#sys.exit(0)
			return

		server=(root.split("://")[1]).split("/")[0]
		self.root=root
		self.server=server

		self.tobrowse.append(root)
        

	def write_to_box(self,msg):

                #wx.Yield();
                self.box.Freeze()
                self.box.BeginSuppressUndo()
		self.box.BeginTextColour((0, 0, 255))
		self.box.WriteText(msg)
		self.box.EndTextColour()
		self.box.Newline()
		self.box.EndSuppressUndo()
		self.box.Thaw()
		#wx.Yield()
	
        def write_to_box_no_nl(self,msg):

                #wx.Yield();
                self.box.Freeze()
                self.box.BeginSuppressUndo()
                self.box.BeginTextColour((0, 0, 255))
                self.box.WriteText(msg)
                self.box.EndTextColour()
                self.box.EndSuppressUndo()
                self.box.Thaw()
                #wx.Yield()
	
	def clear(self):
		self.box.Clear()



	
	def setTimeOut(self,timeout=6):
	  	"""Set the timeout in seconds to wait for a page"""
		self.timeout=timeout

	def setProxy(self,proxy={}):
	  	"""Set proxy preferences"""
		self.proxy=proxy

	def addStartURL(self,url):
		if(self.checklink(url)):
			#print "Invalid link argument:",url
                        #self.box.AppendText("Invalid link argument:")
			wx.CallAfter(self.write_to_box,"Invalid link argument:"+url)
			#sys.exit(0)
			return
		if(self.inzone(url)==0):
			self.tobrowse.append(url)

	def addExcludedURL(self,url):
	  	"""Add an url to the list of forbidden urls"""
		self.excluded.append(url)

	def setCookieFile(self,cookie):
	  	"""Set the file to read the cookie from"""
		self.cookie=cookie

	def setAuthCredentials(self,auth_basic):
		self.auth_basic=auth_basic

	def addBadParam(self,bad_param):
		self.bad_params.append(bad_param)

	def browse(self,url):
		"""Extract urls from a webpage and add them to the list of urls to browse if they aren't in the exclusion list"""
		# We don't need destination anchors
		current=url.split("#")[0]
		# Url without query string
		current=current.split("?")[0]
		# Get the dirname of the file
		currentdir="/".join(current.split("/")[:-1])+"/"

		# Timeout must not be too long to block big documents (for exemple a download script)
		# and not too short to give good results
		socket.setdefaulttimeout(self.timeout)
		try:
			req = urllib2.Request(url)
			u = urllib2.urlopen(req)
		# BadStatusLine can happen when no HTTP status code is given or when a connexion is suddenly closed
		except urllib2.httplib.BadStatusLine:
			#print "Error reading response"
			wx.CallAfter(self.write_to_box,"Error reading response")
		        self.timeToQuit.set()
			return 0
		except IOError,e:
		        #print "\n"+url+":",e
		        wx.CallAfter(self.write_to_box,url+":"+str(e))
			self.excluded.append(url)
			return 0
		proto=url.split("://")[0]
		if proto=="http" or proto=="https":
			# Check the content-type first
			if not u.info().get("Content-Type"):
				# Sometimes there's no content-type... so we rely on the document extension
				if (current.split(".")[-1] not in self.allowed) and current[-1]!="/":
					return 1
			elif u.info().get("Content-Type").find("text")==-1:
				return 1
		# Manage redirections
		if u.headers.dict.has_key("location"):
			redir=self.correctlink(u.headers.dict["location"],current,currentdir,proto)
			if redir!=None:
				if(self.inzone(redir)==0):
					# Is the document already visited of forbidden ?
					if (redir in self.browsed) or (redir in self.tobrowse) or self.isExcluded(redir):
						pass
					else:
						# No -> Will browse it soon
						self.tobrowse.append(redir)
		try:
			htmlSource=u.read()
		except socket.timeout:
			htmlSource=""
		p=linkParser()
		try:
			p.feed(htmlSource)
		except HTMLParser.HTMLParseError,err:
			if tidyhere==1:
				options = dict(output_xhtml=1, add_xml_decl=1, indent=1, tidy_mark=0)
				htmlSource=str(tidy.parseString(htmlSource,**options))
				try:
					p.reset()
					p.feed(htmlSource)
				except HTMLParser.HTMLParseError,err:
					pass
			elif BeautifulSouphere==1:
				htmlSource=BeautifulSoup.BeautifulSoup(htmlSource).prettify()
				try:
					p.reset()
					p.feed(htmlSource)
				except HTMLParser.HTMLParseError,err:
					pass
			# last chance
			else:
				p.liens=re.findall('href="(.*?)"',htmlSource)

		for lien in p.uploads:
			self.uploads.append(self.correctlink(lien,current,currentdir,proto))
		for lien in p.liens:
			lien=self.correctlink(lien,current,currentdir,proto)
			if lien!=None:
				if(self.inzone(lien)==0):
					# Is the document already visited of forbidden ?
					if (lien in self.browsed) or (lien in self.tobrowse) or self.isExcluded(lien):
						pass
					else:
						# No -> Will browse it soon
						self.tobrowse.append(lien)
		for form in p.forms:
			action=self.correctlink(form[0],current,currentdir,proto)
			if action==None: action=current
			form=(action,form[1],url)
			if form not in self.forms: self.forms.append(form)
		# We automaticaly exclude 404 urls
		if u.code==404:
			self.excluded.append(url)
			return 0
		return 1
	

	def correctlink(self,lien,current,currentdir,proto):
	  	"""Transform relatives urls in absolutes ones"""
		# No leading or trailing whitespaces
		lien=lien.strip()
		# bad protocols
		if lien.find("telnet:",0)==0 or lien.find("ftp:",0)==0 or lien.find("mailto:",0)==0 or \
		lien.find("javascript:",0)==0 or lien.find("news:",0)==0 or lien.find("file:",0)==0 or \
		lien.find("gopher:",0)==0 or lien.find("irc:",0)==0 or lien=="":
			return None
		# Good protocols or relatives links
		else:
			# full url, nothing to do :)
			if (lien.find("http://",0)==0) or (lien.find("https://",0)==0):
				pass
			else:
				# root-url related link
				if(lien[0]=='/'):
					lien=proto+"://"+self.server+lien
				else:
					# same page + query string
					if(lien[0]=='?'):
						lien=current+lien
					# current directory related link
					else:
						lien=currentdir+lien
			# No destination anchor
			if lien.find("#")!=-1:
				lien=lien.split("#")[0]
			# reorganize parameters in alphabetical order
			if lien.find("?") != -1:
				args=lien.split("?")[1]
				if args.find("&") != -1 :
					args=args.split("&")
					args.sort()
					args=[i for i in args if i!="" and i.find("=")>=0]
					for i in self.bad_params:
						for j in args:
							if j.startswith(i+"="): args.remove(j)
					args="&".join(args)

				# a hack for auto-generated Apache directory index
				if args in ["C=D;O=A","C=D;O=D","C=M;O=A","C=M;O=D","C=N;O=A","C=N;O=D","C=S;O=A","C=S;O=D"]:
					lien=lien.split("?")[0]
				else:
					lien=lien.split("?")[0]+"?"+args
			# Remove the trailing '?' if its presence doesn't make sense
			if lien[-1:]=="?":
				lien=lien[:-1]
			# remove useless slashes
			if lien.find("?")!=-1:
				file=lien.split("?")[0]
				file=re.sub("[^:]//+","/",file)
				lien=file+"?"+lien.split("?")[1]
			# links going to a parrent directory (..)
			while re.search("/([~:!,;a-zA-Z0-9\.\-+_]+)/\.\./",lien)!=None:
				lien=re.sub("/([~:!,;a-zA-Z0-9\.\-+_]+)/\.\./","/",lien)
			lien=re.sub("/\./","/",lien)
			# Everything is good here
			return lien

	def checklink(self,url):
	  	"""Verify the protocol"""
		if (url.find("http://",0)==0) or (url.find("https://",0)==0):
			return 0
		else:
			return 1

	def inzone(self,url):
		"""Make sure the url is under the root url"""
		temp=self.root
		if isinstance(temp, unicode):
			temp=str(temp.encode("iso8859-15"))
		if(url.find(temp,0)==0):
			return 0
		else:
			return 1
	
	def isExcluded(self,url):
	  	"""Return True if the url is not allowed to be scan"""
	  	match=False
	  	for regexp in self.excluded:
		  	if self.reWildcard(regexp,url):
			  	match=True
		return match
		  
	def reWildcard(self,regexp,string):
	  	"""Wildcard-based regular expression system"""
		regexp=re.sub("\*+","*",regexp)
		match=True
		if regexp.count("*")==0:
			if regexp==string:
				return True
			else:
				return False
		blocks=regexp.split("*")
		start=""
		end=""
		if not regexp.startswith("*"):
			start=blocks[0]
		if not regexp.endswith("*"):
			end=blocks[-1]
		if start!="":
			if string.startswith(start):
				blocks=blocks[1:]
			else:
				return False
		if end!="":
			if string.endswith(end):
				blocks=blocks[:-1]
			else:
				return False
		blocks=[block for block in blocks if block!=""]
		if blocks==[]:
			return match
		for block in blocks:
			i=string.find(block)
			if i==-1: return False
			string=string[i+len(block):]
		return match

	def go(self):

                wx.CallAfter(self.clear)

		# while url list isn't empty, continue browsing
                # if the user stop the scan with Ctrl+C, give him all found urls
		while len(self.tobrowse)>0:
		    if self.timeToQuit.isSet():
		      #print "stopped"
		      del self.tobrowse[0:]
		      break
		    lien=self.tobrowse.pop(0)
		    #print "lswww:lien"+lien
		    if (lien not in self.browsed):
		      if self.browse(lien):
		        self.browsed.append(lien)
			if self.verbose==1:
			  #sys.stderr.write('.')
                          #self.box.AppendText(".")
		          wx.CallAfter(self.write_to_box_no_nl,".")
			elif self.verbose==2:
			  #sys.stderr.write(lien+"\n")
			  #self.box.AppendText(lien+"\n")
                          wx.CallAfter(self.write_to_box,lien)
	        del self.tobrowse[0:] 


	def verbosity(self,vb):
	  	"""Set verbosity level"""
		self.verbose=vb

	def printLinks(self):
	  	"""Print found URLs on standard output"""
		self.browsed.sort()
		sys.stderr.write("\n+ URLs :\n")
		for lien in self.browsed:
			print lien

	def printForms(self):
	  	"""Print found forms on standard output"""
		if self.forms!=[]:
			sys.stderr.write("\n+ Forms Info :\n")
			for form in self.forms:
				print "From:",form[2]
				print "To:",form[0]
				for k,v in form[1].items():
					print "\t"+k,":",v
				print

	def printUploads(self):
	  	"""Print urls accepting uploads"""
		if self.uploads!=[]:
			sys.stderr.write("\n+ Upload Scripts :\n")
			for up in self.uploads:
				print up

	def getLinks(self):
		self.browsed.sort()
		return self.browsed

	def getForms(self):
		return self.forms

	def getUploads(self):
		self.uploads.sort()
		return self.uploads
	
class linkParser(HTMLParser.HTMLParser):
	"""Extract urls in 'a' href HTML tags"""
	def __init__(self):
		HTMLParser.HTMLParser.__init__(self)
		self.liens=[]
		self.forms=[]
		self.form_values={}
		self.inform=0
		self.current_form_url=""
		self.uploads=[]
		self.current_form_method="get"

	def handle_starttag(self,tag,attrs):
		tmpdict={}
		val=None
		for k,v in dict(attrs).items():
			tmpdict[k.lower()]=v
		if tag.lower()=='a':
			if "href" in tmpdict.keys():
				self.liens.append(tmpdict['href'])
	
                if tag.lower()=='form':
			self.inform=1
			self.form_values={}
			if "action" in tmpdict.keys():
				self.liens.append(tmpdict['action'])
				self.current_form_url=tmpdict['action']

			# Forms use GET method by default
			self.current_form_method="get"
			if "method" in tmpdict.keys():
				if tmpdict["method"].lower()=="post":
					self.current_form_method="post"

		if tag.lower()=='input':
			if self.inform==1:
				if "type" not in tmpdict.keys():
					tmpdict["type"]="text"
				if "name" in tmpdict.keys():
					if tmpdict['type'].lower() in ['text','password','radio','checkbox','hidden','submit','search']:
					# use default value if present or set it to 'on'
						if "value" in tmpdict.keys():
							if tmpdict["value"]!="": val=tmpdict["value"]
							else: val="on"
						else: val="on"
						self.form_values.update(dict([(tmpdict['name'],val)]))
					if tmpdict['type'].lower()=="file":
						self.uploads.append(self.current_form_url)

		if tag.lower() in ["textarea","select"]:
			if self.inform==1:
				if "name" in tmpdict.keys():
					self.form_values.update(dict([(tmpdict['name'],'on')]))

		if tag.lower() in ["frame","iframe"]:
			if "src" in tmpdict.keys():
				self.liens.append(tmpdict['src'])

	def handle_endtag(self,tag):
		if tag.lower()=='form':
			self.inform=0
			if self.current_form_method=="post":
				self.forms.append((self.current_form_url,self.form_values))
			else:
				l=["=".join([k,v]) for k,v in self.form_values.items()]
				l.sort()
				self.liens.append(self.current_form_url.split("?")[0]+"?"+"&".join(l))


if __name__ == "__main__":
  try:
	prox={}
	auth=[]
	if len(sys.argv)<2:
		print lswww.__doc__
		sys.exit(0)
	if '-h' in sys.argv or '--help' in sys.argv:
	  print lswww.__doc__
	  sys.exit(0)
	myls=lswww(sys.argv[1])
	myls.verbosity(1)
	try:
	  opts, args = getopt.getopt(sys.argv[2:], "hp:s:x:c:a:r:v:t:",
	      ["help","proxy=","start=","exclude=","cookie=","auth=","remove=","verbose=","timeout="])
	except getopt.GetoptError,e:
	  print e
	  sys.exit(2)
	for o,a in opts:
	  if o in ("-h", "--help"):
	    print lswww.__doc__
	    sys.exit(0)
	  if o in ("-s","--start"):
	    if (a.find("http://",0)==0) or (a.find("https://",0)==0):
	      myls.addStartURL(a)
	  if o in ("-x","--exclude"):
	    if (a.find("http://",0)==0) or (a.find("https://",0)==0):
	      myls.addExcludedURL(a)
	  if o in ("-p","--proxy"):
	    if (a.find("http://",0)==0) or (a.find("https://",0)==0):
	      prox={'http':a}
	      myls.setProxy(prox)
	  if o in ("-c","--cookie"):
	    myls.setCookieFile(a)
	  if o in ("-r","--remove"):
	    myls.addBadParam(a)
	  if o in ("-a","--auth"):
	    if a.find("%")>=0:
	      auth=[a.split("%")[0],a.split("%")[1]]
	      myls.setAuthCredentials(auth)
	  if o in ("-v","--verbose"):
	    if str.isdigit(a):
	      myls.verbosity(int(a))
	  if o in ("-t","--timeout"):
	    if str.isdigit(a):
	      myls.setTimeOut(int(a))
	myls.go()
	myls.printLinks()
	myls.printForms()
	myls.printUploads()
  except SystemExit:
	pass
