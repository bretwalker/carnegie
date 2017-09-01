import json
import csv
import urllib.request
import ssl
import re
import csv
import io
import collections
import pymysql
import pymysql.cursors
import redis
import os
import operator
import sys
from hashlib import blake2b
from datetime import datetime
from datetime import timedelta

pymysql.install_as_MySQLdb()
	
INSERT_SQL = ""
DELETE_SQL = ""
LIMIT = -1

if 'AWS_REGION' not in os.environ:
	redisCn = redis.StrictRedis(host='127.0.0.1', port=6379, db=0)
else:
	redisCn = redis.StrictRedis(host='incident-cache.aqsren.ng.0001.use1.cache.amazonaws.com', port=6379, db=0)

def get_insert(table, header):
	# Generate the SQL for inserting rows
	header.append('insert_timestamp')

	field_names = ', '.join(header)
	field_markers = ', '.join('%s' for col in header)
	return 'INSERT INTO %s (%s) VALUES (%s);' % (table, field_names, field_markers)


def get_delete(table):
	return 'DELETE FROM %s WHERE incident_number = %s;' % (table, '%s')


def format_header(row):
	"""Format column names to remove illegal characters and duplicates
	"""
	safe_col = lambda s: re.sub('\W+', '_', s.lower()).strip('_')
	header = []
	counts = collections.defaultdict(int)
	for col in row:
		col = safe_col(col)
		counts[col] += 1
		if counts[col] > 1:
			col = '{}{}'.format(col, counts[col])
		header.append(col)
	return header


def parse_csv(input_file, user, password, host, table, database, max_inserts=10000):
	print("Importing `%s' into MySQL database `%s.%s'" % (input_file, database, table))

	context = ssl._create_unverified_context()

	#with open("/Users/scottdaugherty/Documents/Alexa/Louisville/carnegie/data/Crime_Data_2017_1__Aug_31.cs") as response:
	#	reader = csv.reader(response, dialect='excel', delimiter=',', quotechar='"', skipinitialspace=True)
	with urllib.request.urlopen(input_file, context=context) as response:
		csv_str = io.StringIO(response.read().decode('utf-8'))
		reader = csv.reader(csv_str, dialect='excel', delimiter=',', quotechar='"', skipinitialspace=True)

		# process header, generate SQL
		header = format_header(next(reader, None))

		global INSERT_SQL
		INSERT_SQL = get_insert(table, header)
		global DELETE_SQL
		DELETE_SQL = get_delete(table)

		# this appears to sort from the second row of the file (which is ideal) since next() was called above
		# TODO test the above assumption
		print("sorting reader...")
		#reader = sorted(reader, key=lambda row: row[0], reverse=False)
		reader = sorted(reader, key=operator.itemgetter(0), reverse=False)
		print("sorting reader complete")
	incidents = []

	try:
		db = pymysql.connect(host=host, user=user, passwd=password, db=database, charset='utf8', autocommit=False)

		with db.cursor() as cursor:	
			for i, row in enumerate(reader):
				if i == 0 or row[0] == incidents[0][0]:
					# incident # of this row matches that of the last row
					incidents.append(row)
				else:
					# new incident #; process the previous incident rows
					processIncident(incidents, cursor, db)

					# reset
					incidents = []
					incidents.append(row)
					
					if LIMIT > 0 and i >= LIMIT:
						break

			# final entry
			processIncident(incidents, cursor, db)

		print('Done!')
	except:
		print("Unexpected error:", sys.exc_info())
	finally:
		db.close()


def processIncident(incidents, cursor, db):
	incidentText = ""
	# concat the column data from every row pertaining to this incident (minus the ID column as it changes with every new file)
	for incident in incidents:
		incidentText += ",".join(incident[0:-1])

	incidentNum = incidents[0][0]
	hashText = hash_it(incidentText)

	incidentExists, incidentAltered = checkIncident(incidentNum, hashText, db)

	if incidentExists:
		if incidentAltered:
			deleteIncident(incidentNum, cursor, db)
			insertIncidents(incidents, hashText, cursor, db)
	else:
		insertIncidents(incidents, hashText, cursor, db)


def checkIncident(incidentNum, hashText, db):
	# three possible scenarios:
	# 1) inc isn't present in redis; return False, False (results in insert to mysql and redis)
	# 2) inc is present in redis and hash matches; return True, False (results in no changes in database or cache)
	# 3) inc is present in redis but hash does not match; return True, True (delete from mysql and redis, insert as in step 1)
	incidentExists = False
	incidentAltered = False

	hashLookup = redisCn.get(incidentNum)

	if hashLookup != None:
		hashLookup = hashLookup.decode("utf-8")
		incidentExists = True

		if(hashLookup != hashText):
			incidentAltered = True

	return incidentExists, incidentAltered


def insertIncidents(incidents, hashText, cursor, db):
	no_exceptions = True

	# load into MYSQL
	for incident in incidents:
		# TODO why is this padding necessary?
		while len(incident) < 15: #len(header):
			incident.append('') # this row is missing columns so pad blank values

		incident.append(datetime.now())

		try:
			cursor.execute(INSERT_SQL, incident)
		except Exception as e:
			print('Error inserting incident: %s' % (incidents[0][0]))
			print(e)
			no_exceptions = False
			break
	
	if(no_exceptions):
		db.commit()
		# set Redis key/value	
		redisCn.set(incidents[0][0], hashText)
		#print(incidents[0][0] + ',', end='')
		print('Inserted %s' % (incidents[0][0]))
	else:
		db.rollback()


def deleteIncident(incidentNum, cursor, db):
	try:
		# delete from MYSQL
		cursor.execute(DELETE_SQL, incidentNum)
		db.commit()
		# delete from Redis
		redisCn.delete(incidentNum)

		print("Incident deleted: %s" % (incidentNum))

	except Exception as e:
		print('Error deleting incident: %s' % incidentNum)
		print(e)
	except:
		print("Unexpected error: ", sys.exc_info())
	

def get_crime_datasets():
	
	context = ssl._create_unverified_context()
	
	distributions = []
	
	with urllib.request.urlopen("https://data.louisvilleky.gov/data.json", context=context) as data_file:
		data = json.load(data_file)
		
		crime_dataset = [dataset for dataset in data["dataset"] 
			if dataset["identifier"] == "a0c75ea8-ef9e-458b-91a2-b9e42013009f"] #Crime Data identifier
		
		distributions = [ distribution for distribution in crime_dataset[0]["distribution"]]
			
		print(distributions[0]["title"])
	
	return distributions


def hash_it(input):
	h = blake2b(digest_size=20)
	h.update(bytearray(input, 'utf-8'))
	return h.hexdigest()


def get_csv_file_name():
	context = ssl._create_unverified_context()
	with urllib.request.urlopen("https://data.louisvilleky.gov/api/3/action/package_show?id=crime-data", context=context) as data_file:
		data = json.load(data_file)

		file_name = data["result"][0]["resources"][0]["url"]
		return file_name


def lambda_handler(event, context):
	startTime = datetime.now()

	print("Execution for %s" % startTime)

	crimefile = get_csv_file_name()
	if("2017" in crimefile):
		parse_csv(crimefile, 'rw', 'civicdataalliance', 'civicdata.crogewynsqom.us-east-1.rds.amazonaws.com', 'crimeDataQA', 'louisvilleky', max_inserts=10)

	diffMinutes = (datetime.now() - startTime) / timedelta(minutes=1)
	print("Execution time: %dm:%ds" % (diffMinutes, diffMinutes * 60))

	return "handler completed"


if 'AWS_REGION' not in os.environ:
	lambda_handler(None, None)