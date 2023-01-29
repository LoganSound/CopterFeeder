#!/usr/bin/env python3

'''
Upload rotorcraft positions to Helicopters of DC
'''

#import json

import csv

# unused

#from datetime import timezone

import datetime

import logging
import argparse
import sys

from time import sleep

import daemon


#import urllib
import requests

# used for getting MONGOPW and MONGOUSER
from dotenv import dotenv_values, set_key


# only need one of these
import pymongo
#from pymongo import MongoClient


## YYYYMMDD_HHMM_REV
VERSION = 20220129_0815_001

logger = logging.getLogger(__name__)


# Hard Coding User/Pw etc is bad umkay
# Should be pulling thse from env
#    FEEDER_ID = ""
#    AIRPLANES_FOLDER = "adsbexchange-feed"
#    # FR24: dump1090-mutability
#    # ADSBEXchange location: adsbexchange-feed
#    # Readsb location: readsb
#    MONGOUSER = ""
#    MONGOPW = ""


# Deprecated with "requests" pull to localhost:8080
# AIRPLANES_FOLDER = "dump1090-fa"
# FR24: dump1090-mutability
# ADSBEXchange location: adsbexchange-feed
# Readsb location: readsb


def mongo_insert(mydict):
    '''
    Insert one entry into Mongo db
    '''

#   password = urllib.parse.quote_plus(MONGOPW)

    #   This needs to be wrapped in a try/except
    myclient = pymongo.MongoClient(
        "mongodb+srv://" +
        MONGOUSER +
        ":" +
        MONGOPW +
        "@helicoptersofdc.sq5oe.mongodb.net/?retryWrites=true&w=majority")

    mydb = myclient["HelicoptersofDC"]
    mycol = mydb["ADSB"]

    #   This needs to be wrapped in a try/except
    ret_val = mycol.insert_one(mydict)

    return ret_val


def update_helidb():
    ''' Main '''


    logger.info('Updating Helidb at %s', datetime.datetime.now())

    try:

#        with open("/run/" + AIRPLANES_FOLDER + "/aircraft.json") as json_file:
#        data = json.load(json_file)
#       planes = data["aircraft"]

#       Use this if checking returns from the request
#       req = requests.get('http://localhost:8080/data/aircraft.json')
#       planes = req.json()["aircraft"]

#       use this if assuming the request succeeds and spits out json
        planes = requests.get(AIRCRAFT_URL, timeout=5).json()["aircraft"]

    except (ValueError, UnboundLocalError, AttributeError) as err:
        logger.error("JSON Decode Error: %s", err)

    logger.debug("Aircraft to check: %d", len(planes))


    for plane in planes:
        output = ""

        # There is a ts in the json output - should we use that?
#        dt = ts = datetime.datetime.now().timestamp()
        dt_stamp = datetime.datetime.now().timestamp()

        output += str(dt_stamp)
        callsign = ""
        heli_type = ""

        try:
            iaco_hex = str(plane["hex"]).lower()
            heli_type = find_helis(iaco_hex)
            output += " " + heli_type
        except BaseException:
            output += " no type or reg"

        if "category" in plane and plane["category"] == "A7": 
            logger.info("Aircraft: %s appears be rotorcraft - Category: %s", iaco_hex, plane["category"])

        if heli_type == "" or heli_type is None :
            logger.debug('%s Not a known rotorcraft ', iaco_hex)
            continue

        logger.debug("Parsing Helicopter: %s", iaco_hex)

        try:
            callsign = str(plane["flight"]).strip()
            output += " " + callsign
        except BaseException:
            output += " no call"

        try:

            # Assumtion is made that negative altitude is unlikely
            # Using max() here removes negative numbers

            alt_baro = max(0,int(plane["alt_baro"]))

            # FR altitude

            output += " " + str(alt_baro)

        except BaseException:
            alt_baro = None

        try:
            alt_geom = max(0,int(plane["alt_geom"]))
            # FR altitude
            output += " " + str(alt_geom)
        except BaseException:
            alt_geom = None

        try:
            head = float(plane["r_dir"])
            # readsb/FR "track"
            output += " " + str(head)
        except BaseException:
            head = None
            output += " no heading"
        try:
            lat = float(plane["lat"])
            lon = float(plane["lon"])
            output += " " + str(lat) + "," + str(lon)

        except BaseException:
            lat = None
            lon = None
        try:
            squawk = str(plane["squawk"])
            output += " " + squawk
        except BaseException:

            squawk = ""
            output += " no squawk"

        logger.info("Heliopter Reported %s: %s", plane["hex"], output )

        if copter_logger:
            copter_logger.info("Heliopter Reported %s: %s", plane["hex"], output )

        if heli_type != "":
            mydict = {"type": "Feature",
                      "properties": { "date": dt_stamp,
                                      "icao": iaco_hex,
                                      "type": heli_type,
                                      "call": callsign,
                                      "heading": head,
                                      "squawk": squawk,
                                      "altitude_baro": alt_baro,
                                      "altitude_geo": alt_geom,
                                      "feeder": FEEDER_ID},
                      "geometry": {"type": "Point", "coordinates": [lon, lat]}
                      }
            ret_val = mongo_insert(mydict)
            # if ret_val: ... do something


def find_helis_old(iaco_hex):
    '''
        Deprecated
        Check if an iaco hex code is in Bills catalog of DC Helicopters
        returns the type of helicopter if known
    '''

    with open("bills_operators.csv", encoding='UTF-8') as csvfile:
        opsread = csv.DictReader(csvfile)
        heli_type = ""
        for row in opsread:
            if iaco_hex.upper() == row["hex"]:
                heli_type = row["type"]
        return heli_type


def find_helis( iaco_hex ):
    '''
        check if iaco is known and return type or empty string
    '''
    logger.debug("Checking for: %s", iaco_hex)
    if heli_types[iaco_hex]:
        return heli_types[iaco_hex]

    return ""


def load_helis_from_file(heli_file):
    '''
        Read Bills catalog of DC Helicopters into array
        returns dictionary of helis and types
    '''
    helis_dict = {}
    with open(heli_file, encoding='UTF-8') as csvfile:
        opsread = csv.DictReader(csvfile)
        for row in opsread:
            helis_dict[row["hex"].lower()] = row["type"]
            logger.debug("Loaded %s :: %s", row["hex"].lower(), row["type"] )
        return helis_dict




def run_loop(interval):
    '''
        Run as loop and sleep specified interval
    '''

    while True:

        logger.debug("Starting Update")

        update_helidb()

        logger.debug('sleeping %s...',interval)

        sleep(interval)


if __name__ == '__main__':


    # Read Environment 

    config = dotenv_values(".env")


    parser = argparse.ArgumentParser(description="Helicopters of DC data loader")
    parser.add_argument("-V","--version", help="Print version and exit",
                         action="store_true", default=False)
    parser.add_argument("-v","--verbose", help="Emit Verbose message stream",
                         action="store_true", default=False)
    parser.add_argument("-D","--debug", help="Emit Debug messages",
                         action="store_true", default=False)

    parser.add_argument("-d","--daemon", help="Run as a daemon",
                         action="store_true", default=False)

    parser.add_argument("-o","--once", help="Run once and exit",
                         action="store_true", default=False)

    parser.add_argument("-l","--log", help="File for logging reported rotorcraft",
                         action="store", default=None)

    parser.add_argument("-i","--interval", help="Interval between cycles in seconds",
                         action="store", type=int, default=60)

    parser.add_argument("-s","--server", help="dump1090 server hostname (default localhost)",
                         nargs=1, action="store", default=None)

    parser.add_argument("-p","--port", help="alt-http port on dump1090 server (default 8080)",
                         action="store", type=int, default=None)

    parser.add_argument("-u","--mongouser", help="MONGO DB User",
                         action="store", default=None)
    parser.add_argument("-P","--mongopw", help="Mongo DB Password",
                         action="store", default=None)
    parser.add_argument("-f","--feederid", help="Feeder ID",
                         action="store", default=None)

    args = parser.parse_args()


    if args.version:
        print(f"{parser.prog} version: {VERSION}")
        sys.exit()

    logging.basicConfig(level=logging.WARN)

    if args.verbose:
#        ch=logging.StreamHandler()
#        ch.setLevel(logging.INFO)
#        logger.addHandler(ch)

        logger.setLevel(logging.INFO)

    if args.debug:
#        ch=logging.StreamHandler()
#        ch.setLevel(logging.DEBUG)
#        logger.addHandler(ch)

        logger.setLevel(logging.DEBUG)


    if args.log:

	# opens a second logging instance specifically for logging noted copters "output"
        copter_logger = logging.getLogger('copter_logger')
        cl=logging.FileHandler(args.log)
        cl.setLevel(logging.INFO)
        copter_logger.addHandler(cl)


    # Should be pulling these from env

    if args.feederid:
        FEEDER_ID = args.feederid
    elif "FEEDER_ID" in config:
        FEEDER_ID = config["FEEDER_ID"]
    else: 
        FEEDER_ID = None
        logger.error("No FEEDER_ID Found - Exiting")
        sys.exit()

    if args.server:
        server = args.server
    elif 'SERVER' in config:  
        server = config["SERVER"]
    else:
        server = 'localhost'

    #reqUrl = f"{base_url}/api/token/"

    if args.port:
        port = args.port
    elif 'PORT' in config:  
        port = config["PORT"]
    else:
         port = 8080

    AIRCRAFT_URL=f'http://{server}:{port}/data/aircraft.json'

    logger.debug("Using AIRCRAFT_URL: %s", AIRCRAFT_URL) 



    if args.mongopw:
        MONGOPW = args.mongopw
    elif 'MONGOPW' in config:
        MONGOPW = config['MONGOPW']
    else:
        MONGOPW = None
        logger.error("No Mongo PW Found - Exiting")
        sys.exit()

    if args.mongouser:
        MONGOUSER = args.mongouser
    elif 'MONGOUSER' in config:
        MONGOUSER = config['MONGOUSER']
    else:
        MONGOUSER = None
        logger.error("No Mongo User Found - Exiting")
        sys.exit()

# probably need to have an option for different file names

    heli_types = {}

    heli_types = load_helis_from_file("bills_operators.csv")

    if args.once:
        update_helidb()
        sys.exit()

    if args.daemon:

        with daemon.DaemonContext():
            run_loop(args.interval)
    else:

        try:
            logger.debug("Starting main processing loop")
            run_loop(args.interval)

        except KeyboardInterrupt:
            logger.warning("Received Keyboard Interrupt -- Exiting...")
            sys.exit()
