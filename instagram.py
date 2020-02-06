import requests
import json
from bs4 import BeautifulSoup
import re
import json
import threading
import sys
import os
from pathlib import Path

headers={
	"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20100101 Firefox/71.0"
}

def get_max_id(folder):
	max = ''
	for item in os.listdir(folder):
		reNumber = re.compile("(\d+).jpg")
		groups = reNumber.findall(item)
		if groups:
			id = groups[0]
			if id > max:
				max = id
	return max

def download(url_list,folder):
	headers ={
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:70.0) Gecko/20100101 Firefox/70.0"
	}
	for item in url_list:
		name = "{}.jpg".format(item['media_id'])
		path = Path(folder)/name
		req = requests.get(item['display_url'],headers=headers)
		print("Downloading {}...".format(name))
		f = open(path,'wb')
		f.write(req.content)
		f.close()

def thread_download(url_list,folder,workers):
    downloadThreads=[]
    n_work = len(url_list)
    workload = n_work//workers+1
    i=0
    while(i<n_work):
        downloadThread = threading.Thread(target = download,args=(url_list[slice(i,i+workload)],folder))
        downloadThreads.append(downloadThread)
        downloadThread.start()
        i+=workload
    for downloadThread in downloadThreads:
        downloadThread.join()

def parseUrl(link,headers):
	req = requests.get(link,headers=headers)
	soup = BeautifulSoup(req.text,"html.parser")
	data = soup.body.find("script").get_text()
	# strip the variable name
	pattern = re.compile(r"window._sharedData\s=\s")
	data = pattern.sub("",data)
	#strip the semicolon character
	pattern = re.compile(r".$")
	data = pattern.sub("",data)
	return json.loads(data)

class instagram_api():
	def __init__(self,profileName):
		self.profileName = profileName
		self.queryHash = "e769aa130647d2354c40ea6a439bfc08"
		self.headers={
			"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20100101 Firefox/71.0"
		}
		self.cursor = None
		self.userInfo = None

	def parsePage(self):
		if self.cursor:
			fetchUrl = self.getUrlStr()
			req = requests.get(fetchUrl,headers=self.headers)
			self.jsonData = json.loads(req.text)
		else:
			fetchUrl = "https://www.instagram.com/{}/".format(self.profileName)
			self.jsonData = parseUrl(fetchUrl,headers=self.headers)
		#parsing user information
		if not self.userInfo:
			userInfo={}
			userData = self.jsonData['entry_data']['ProfilePage'][0]['graphql']['user']
			userInfo['id'] = userData['id']
			userInfo['biography'] = userData['biography']
			userInfo['full_name'] = userData['full_name']
			userInfo['profile_pic_url'] = userData['profile_pic_url_hd']
			userInfo['follower_by'] = userData['edge_followed_by']['count']
			userInfo['follow'] = userData['edge_follow']['count']
			self.userInfo = userInfo


	def parseProfilePage(self):
		profilePage ="https://www.instagram.com/{}/".format(self.profileName)
		jsonData = parseUrl(profilePage,headers=self.headers)
		self.jsonData = jsonData

	def parseLastCursor(self):
		if 'data' in self.jsonData.keys():
			pageInfo = self.jsonData['data']['user']['edge_owner_to_timeline_media']['page_info']
		else:
			pageInfo = self.jsonData['entry_data']['ProfilePage'][0]['graphql']['user']\
				['edge_owner_to_timeline_media']['page_info']
		if pageInfo['has_next_page']:
			self.cursor = pageInfo['end_cursor'].replace('=','%3D')
		else:
			self.cursor = None

	def getMedia(self):
		if "data" in self.jsonData.keys():
			posts = self.jsonData['data']['user']['edge_owner_to_timeline_media']['edges']
		else:
			posts = self.jsonData['entry_data']['ProfilePage'][0]['graphql']['user']\
				['edge_owner_to_timeline_media']['edges']
		mediaList=[]

		for post in posts:
			nodeList=[]
			node = post['node']
			if node['__typename']=="GraphImage":
				nodeList=[node]
			elif node['__typename']=="GraphSidecar":
				if "edge_sidecar_to_children" in node.keys():
					sidecar = node["edge_sidecar_to_children"]['edges']
				else:
					url = "https://www.instagram.com/p/{}/".format(node['shortcode'])
					jsonData = parseUrl(url,headers=headers)
					sidecar = jsonData['entry_data']['PostPage'][0]['graphql']['shortcode_media']\
							['edge_sidecar_to_children']['edges']
				for child in sidecar:
					nodeList.append(child['node'])

			for node in nodeList:
				mediaInfo = {
					"display_url":node['display_url'],
					"media_id":node['id'],
					"dimensions":node['dimensions'],
					"type":"image"
				}
				mediaList.append(mediaInfo)
		self.mediaList = mediaList

	def getUrlStr(self):
		return "https://www.instagram.com/graphql/query/?query_hash={}&variables=%7b%22id%22%3a%22{}%22%2c%22first%22%3a12%2c%22after%22%3a%22{}%22%7d".format(self.queryHash,self.userInfo['id'],self.cursor)

def writeConfig():
	queryHash ="e769aa130647d2354c40ea6a439bfc08"
	if Path("insta_config.json").exists():
		print("Config file found. Do you want to rewrite your config file?")
		while True:
			confirm = input("Select(y/n): ")
			if confirm == 'n':
				return None
			if confirm == 'y':
				break
	config={}
	while True:
		folder = input("Type your output folder: ")
		config['folder'] = str(Path(folder))
		changeHash = input("Do you want to use default query hash y/n: ")
		if changeHash == 'y':
			config['queryHash'] = queryHash
		if changeHash == 'n':
			newHash = input("Type your new query hash: ")
			config['queryHash'] = newHash
		confirm = input("Confirm your change y/n/x: ")
		if confirm == 'y':
			break
		if confirm == 'x':
			return None
	f = open("insta_config.json","w")
	json.dump(config,f)
	f.close()
	return config 

def main():
	if (sys.argv[-1] == "c") or (not Path("insta_config.json").exists()):
		config = writeConfig()
	else:
		try:
			configFile = open("insta_config.json","r")
			config = json.load(configFile)
			configFile.close()
		except json.decoder.JSONDecodeError:
			config = writeConfig()
	if config == None:
		print("Cannot read config !")
		return
	queryHash = config['queryHash']
	profileUrl = input("Profile url: ")
	reProfile = re.compile("(?:.*instagram.com\/)*([^\/]+)\/*")
	profileName = reProfile.findall(profileUrl)[0]
	folder = Path(config['folder'])/profileName
	if not folder.exists():
		folder.mkdir(parents=True, exist_ok=True)
	update = False
	if os.listdir(folder):
		while True:
			choice = input("Do you want to update(y/n)?: ")
			if choice == 'y':
				maxId = get_max_id(folder)
				update = True
				break
			if choice == 'n':
				break
	limit = sys.argv[1] if (len(sys.argv) > 1 and sys.argv[1].isnumeric())else None
	app = instagram_api(profileName)
	total = 0
	while True:
		app.parsePage()
		app.getMedia()
		if update:
			for item in app.mediaList:
				if item['media_id'] == maxId:
					thread_download(app.mediaList,folder,8)
					return
		app.parseLastCursor()
		thread_download(app.mediaList,folder,8)
		total+=12
		if (limit and total > int(limit)) or (not app.cursor):
			break

main()