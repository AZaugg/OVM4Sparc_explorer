#!/usr/bin/python
import flask
import pickle
from GatherFacts import *

import mimetypes


app= flask.Flask(__name__)



#####################################################
DC = pickle.load( open( "clusters.pickle", "rb" ) )
#clusters = DC.keys()
#####################################################
# Dunny data so yolu can get off the ground without setup
clusters = ['CLUSTER01', 'CLUSTER02']
cdoms = ['CDOM1','CDOM2','CDOM3','CDOM4','CDOM8']
ldoms = ['ldom1','ldom2','ldom3', 'l']
ldom = ['l']
#####################################################

@app.route('/<cluster>')
def displayCluster(cluster):
	#cdoms = []
	#for item in DC[cluster].nodes:
		#cdoms.append(item.name)
	cdoms.sort()
	return flask.render_template("cluster.html", clusters=clusters, cluster=cluster, cdoms=cdoms)

@app.route('/<cluster>/<cdom>')
def displayCDOM(cluster, cdom):
	#cdoms = []
	#for item in DC[cluster].nodes:
	#	cdoms.append(item.name)
	cdoms.sort()
	return flask.render_template("cdom.html", clusters=clusters, cluster=cluster, cdoms=cdoms, cdom=cdom, ldoms=ldoms)

@app.route('/<cluster>/<cdom>/<ldom>')
def displayLDOM(cluster, cdom, ldom):
	return flask.render_template("cdom.html", clusters=clusters, cluster=cluster, cdoms=cdoms, cdom=cdom, ldoms=ldoms, ldom=ldom)

@app.route('/')
def index():
	print(mimetypes.guess_type('style.css'))

	return flask.render_template("index.html", clusters=clusters)

if __name__ == "__main__":
	app.run(debug=True, host='0.0.0.0')
