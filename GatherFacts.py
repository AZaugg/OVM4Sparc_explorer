#!/usr/bin/python
#
# Gather details of all defined hosts in config.conf file, determine
# what hosts are hosted where and sizes of all hosts.
# 
# Determine remaining and used capacity based on the above data
#
# Written by Andy Zaugg

import ConfigParser, os, pickle, sys, time, glob, Queue, threading, subprocess
from re import search
from optparse import OptionParser

# Globals #
# This will move to a config file eventually
SOURCE = 'SSH' #'XML'
CoreRedundancy = 256 
MemRedundancy = 1024
NumThreads = 2
USERNAME = '' # Username of person that has access to all cdoms

# TODO: Automatically reduct control domains from capacity as CDOMs
# are not usable

class cluster(object):
	def __init__(self, name):
		self.TotalVcpu = 0
		self.Totalmem = 0
		self.name = name
		self.nodes = []
	def __str__(self):
		return name
	def TotalVcpuCapacity(self):
		return self.TotalVcpu - CoreRedundancy
	def TotalMEMCapacity(self):
		return self.Totalmem - MemRedundancy
	def ClusterUsedCPUCapacity(self):
		cpu = 0
		for node in self.nodes:
			cpu = cpu + node.usedCPUCapacity()
		return cpu + 16 # Test overhead
	def ClusterUsedMEMCapacity(self):
		mem = 0
		for node in self.nodes:
			mem = mem + node.usedMEMCapacity()
		return mem + 256 # Test overhead
	def ClusterFreeCPUCapacity(self):
		UsedCPU = self.ClusterUsedCPUCapacity()
		return self.TotalVcpu - UsedCPU - CoreRedundancy + 16 # Test over head of CDOM
	def ClusterFreeMEMCapacity(self):
		UsedMEM = self.ClusterUsedMEMCapacity()
		return self.Totalmem - UsedMEM - MemRedundancy + 256 # Test over head of CDOM
		

#---------------------------------------------
class machine(object):
	def __init__(self, ncpu, mem, name=None, cluster=None):
		self.name = name
		self.ncpu = float(ncpu)
		self.mem = float(mem)
		self.cluster = ""
		self.ldomLst = []

                # If it looks like we have more than 10TB of memory
                # then its measured in KB not GB. Lets convert it.
                if self.mem > 10240:
                        self.mem = self.mem/1024/1024/1024

	def __str__(self):
		print self.name
	def usedCPUCapacity(self):
		# Return the Used capacity of the machine
		# return with VCPU count
		cpu = 0
		for ldom in self.ldomLst:
			cpu = cpu + ldom.ncpu
		return cpu
	def usedMEMCapacity(self):
		# Return the Used capacity of the machine
		mem = 0
		for ldom in self.ldomLst:
			mem = mem + ldom.mem
		return mem
	def freeCPUCapacity(self):
		# report free capacity of a machine
		# return VCPU count
		Usedcpu = self.useCPUCapacity()
		return self.ncpu - Usedcpu
	def freeMEMCapacity(self):
		# report free capacity of a machine
		Memcpu = self.usedMEMCapacity()
		return self.mem - Usedmem
#---------------------------------------------
class iodom(object):
	def __init__(self, ncpu, mem):
		self.ncpu = ncpu
		self.mem = mem
#---------------------------------------------
class cdom(object):
	def __init__(self, ncpu, mem ):
		self.ncpu = ncpu
		self.mem = mem
#---------------------------------------------
class ldom(object):
	def __init__(self, cdom, name, ncpu, mem):
		self.cdom = cdom
		self.name = name
		self.ncpu = ncpu
		self.mem = mem

def SSHGatherFacts(q):
	''' Use SSH to gather facts about all ldoms/cdom on a a control domain gather
		data such as CPU,memory, name, role and append it to machine Class
	'''
	while True:
		target = q.get()
		o = subprocess.Popen(["ssh", "%s@%s" % (USERNAME, target.name), "sudo /usr/sbin/ldm list -p"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		#o = os.popen("ssh -i ~/.ssh/id_rsa-OVM %s@%s 'sudo ldm list -p'" % (USERNAME, target.name)
		ldm = o.stdout.readlines()

		if  o.stderr.readlines():
			print "The following errors were detected with ssh: %s" % o.stderr.readlines()

		for line in ldm:
			# Below REGEX wont find unbound systemsh 
			#ldm =['VERSION 1.11\n', 'DOMAIN|name=primary|state=active|flags=-n-cv-|cons=UART|ncpu=5|mem=47272862140|util=0.4|uptime=4772570|norm_util=0.4\n', 'DOMAIN|name=host1|state=active|flags=-n----|cons=5000|ncpu=1|mem=47272862140|util=1.4|uptime=173837|norm_util=1.4\n', 'DOMAIN|name=host2|state=active|flags=-n----|cons=5001|ncpu=16|mem=47272862140|util=1.4|uptime=1846649|norm_util=1.4\n', 'DOMAIN|name=host3|state=active|flags=-n----|cons=5002|ncpu=16|mem=47272862140|util=1.2|uptime=1847005|norm_util=1.2\n']
			m = search('DOMAIN\|name=(?P<LDOM>\S+)\|state=(?P<STATE>\S+)\|flags=(?P<FLAGS>\S+)\|cons=\S+\|ncpu=(?P<NCPU>\d+)\|mem=(?P<MEM>\d+)\|util=\d+.\d+|uptime=i(?P<UPTIME>\d+)\|norm_util=\d+.\d+$', line)
	
			# if no match, nothng of interest continue on
			if not m:
				continue
	
			# Examine flags of each domain and determine what it is, rember 
			# order is importants, C=cdom, n=normal domain, v=virtual/io domain
			if 'c' in m.group('FLAGS'):
				# Found a control domain
				# Division is to convert unit of measurement bytes to GB
				c = cdom(m.group('NCPU'), m.group('MEM'))
				c.name = m.group('LDOM')
				target.ldomLst.append(c)
			elif 'v' in m.group('FLAGS'):
				# TODO: Implement IODOMAIN support
				pass
			elif 'n' in m.group('FLAGS'):
				# found an ldom in a normal state
				# Division is to convert unit of measurement bytes to GB
				l = ldom(machine, m.group('LDOM'), m.group('NCPU'), m.group('MEM'))
				target.ldomLst.append(l)
		q.task_done()
	
#--------------------------------------------------------------------------------------------------
def GatherData(clusters):
	''' For each known about host, start the gather facts process, we support XML and SSH as gather facts
		methods
	'''

	# Create worker threads
	queue = Queue.Queue()
	for i in range(NumThreads):
		worker = threading.Thread(target=SSHGatherFacts, args=(queue,))
		worker.setDaemon(True)
		worker.start()

	for item in clusters:

		# Put each known about machine onto queue
		# Which will be worked in target=SSHGatherFacts
		for node in clusters[item].nodes:
			queue.put(node)

	# Wait here for comletion of all
	# threads
	queue.join()

	return clusters
#--------------------------------------------------------------------------------------------------
def ReadConfig():
	config = ConfigParser.RawConfigParser()
	clusters = {}

	try:
		config.readfp(open('config.conf'))
		for node in config.sections():
			# Perform some sanity checks on config file if section is
			# not valid skip and continue to next section
			MandatoryOptions = ['cluster', 'cpu' , 'memory']
			if not all(i in MandatoryOptions for i in config.options(node)):
				print "Section: %s: Does not contain all mandetory fields, skipping section"
				continue
			
			# Start a cluster collection
			c = config.get(node, 'cluster')
			if  c not in clusters:
				clusters[c] = cluster(c)
			
			# Populate the object with all facts gathered
			# from config file
			try:
				ncpu = float(config.get(node, 'cpu'))
				mem = float(config.get(node, 'memory'))
			except ValueError:
				print "Invalid entry in confif file"
				sys.exit()
			clusters[c].nodes.append( machine(ncpu, mem, node, cluster) )
			clusters[c].TotalVcpu = clusters[c].TotalVcpu + ncpu
			clusters[c].Totalmem = clusters[c].Totalmem + mem

	except IOError:
		print "Unabel to locate config file"
		sys.exit()
	except ConfigParser.MissingSectionHeaderError:
		print "Invalid config fileNo sections in config file"
		sys.exit()

	return clusters
#--------------------------------------------------------------------------------------------------

if __name__ == "__main__":
	parser = OptionParser()
	parser.add_option("-c", "--cluster", dest="cluster", help="Cluster name", default=None)
	parser.add_option("-l", "--ldom", dest="ldom", help="Ldom name (or all)", default='all')
	parser.add_option("-C", "--cores", dest="Cores", help="Show output in Cores instead of VCPU", default='all')
	(options, args) = parser.parse_args()

	# On App start load data from all CDOMs
	clusters = ReadConfig()

	clusters = GatherData(clusters)
	pickle.dump(clusters, open("clusters.pickle", "wb"))


	for i in clusters:
		print 
		print "Used CPU capacity %f" % clusters[i].ClusterUsedCPUCapacity()
		print "Total MEM capacity %f" % clusters[i].Totalmem
		print "Used MEM capacity %f" % clusters[i].ClusterUsedMEMCapacity()
		print ""
		#print clusters[i].nodesClusterFreeCPUCapacity
		#print clusters[i].TotalVcpu


	print "                             CPU 	           	  MEMORY       "					
	print "Cluster        | Capacity     Used      Free   | Capacity     Used     Free" 
	print "========================================================================"
	for i in clusters:
		print "%s %11.2f %10.2f %8.2f %11.2f %10.2f %10.2f" % (i , clusters[i].TotalVcpuCapacity(), clusters[i].ClusterUsedCPUCapacity(), clusters[i].ClusterFreeCPUCapacity(), clusters[i].TotalMEMCapacity(), clusters[i].ClusterUsedMEMCapacity(), clusters[i].ClusterFreeMEMCapacity() )
	print "========================================================================"

