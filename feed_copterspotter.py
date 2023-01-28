import json
import csv
from datetime import timezone
import datetime
import urllib
import pymongo
from pymongo import MongoClient

def main():
 FEEDER_ID=""
 AIRPLANES_FOLDER="adsbexchange-feed"
 #FR24: dump1090-mutability
 #ADSBEXchange location: adsbexchange-feed
 #Readsb location: readsb
 MONGOUSER=""
 MONGOPW=""

 
 try:
  with open("/run/"+AIRPLANES_FOLDER+"/aircraft.json") as json_file:
   data = json.load(json_file)
   planes = data["aircraft"]
 except (ValueError,UnboundLocalError,AttributeError) as e:
  print("JSON Decode Error")
 for i in planes:
  output=""
  dt = ts = datetime.datetime.now().timestamp()
  output+=str(dt)
  c=""
  t=""
  try:
   hex = str(i["hex"]).lower()
   t = FindHelis(hex)
   output+=" "+t
  except:
   output+=" no type or reg"
  try:
   c = str(i["flight"]).strip()
   output+=" "+c
  except:
   output+=" no call"
  try:
   ab = int(i["alt_baro"])
   #FR altitude
   if ab<0:
    ab=0
   output+=" "+str(ab)
  except:
   ab = None
  try:
   ag = int(i["alt_geom"])
   #FR altitude
   if ag<0:
    ag=0
   output+=" "+str(ag)
  except:
   ag = None
  try:
   head= float(i["r_dir"])
   #readsb/FR "track"
   output+=" "+str(head)
  except:
   head=None
   output+=" no heading"
  try:
   lat = float(i["lat"])
   lon = float(i["lon"])
   output+=" "+str(lat)+","+str(lon)
  except:
   lat = None
   lon = None
  try:
   squawk=str(i["squawk"])
   output+=" "+squawk
  except:
   squawk=""
   output+=" no squawk"
   

  if t!="":
   print(output)
   password = urllib.parse.quote_plus(MONGOPW)
   myclient = pymongo.MongoClient("mongodb+srv://"+MONGOUSER+":"+MONGOPW+"@helicoptersofdc.sq5oe.mongodb.net/?retryWrites=true&w=majority")
   mydb = myclient["HelicoptersofDC"]
   mycol = mydb["ADSB"]

   mydict = { "type":"Feature",
             "properties":{"date": dt, "icao":hex,"type": t, "call": c, "heading": head, "squawk":squawk, "altitude_baro":ab,"altitude_geo":ag,"feeder":FEEDER_ID},
             "geometry":{"type":"Point","coordinates":[lon,lat]}
            }

   x = mycol.insert_one(mydict)

def FindHelis(hex):
 with open("bills_operators.csv") as csvfile:
  opsread=csv.DictReader(csvfile)
  t=""
  for row in opsread:
   if hex.upper()==row["hex"]:
    t= row["type"]
  return t

main()
