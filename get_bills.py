#!/usr/bin/env python3
"""
Slightly Overbloated Python method of pulling the bills_operators.csv file and renaming the older version
"""

import requests
import time

# import json
# import csv

# import pandas

import logging
import os


formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# create formatter

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# dateline = time.strftime('%Y%m%d%H%M%S')

BILLS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv"


def get_bills_operators(bills_url):
    """

    Pulls bills_operators.csv from URL

    """

    bills = requests.get(bills_url)

    logger.info("Status_Code: %s", bills.status_code)

    if bills.status_code == 200:
        with open("bills_operators_tmp.csv", "w", encoding="UTF-8") as tmpcsvfile:
            tmpcsvfile.write(bills.text)
            tmpcsvfile.close()
            bills_age = os.path.getmtime("bills_operators.csv")
            os.rename(
                "bills_operators.csv",
                "bills_operators" + time.strftime("%Y%m%d-%H%M%S") + ".csv",
            )
            os.rename("bills_operators_tmp.csv", "bills_operators.csv")
        return bills_age


if __name__ == "__main__":
    bills_age = os.path.getmtime("bills_operators.csv")

    if int(time.time() - bills_age) >= 86340:  # 24hrs - 1 minute
        logger.info(
            "bills_operators.csv more than 24hrs old: %s", time.ctime(bills_age)
        )
        bills_age = get_bills_operators(BILLS_URL)
        logger.info(f"Updated bills_operators.csv at: %s", time.ctime(bills_age))
    else:
        logger.info(
            "bills_operators.csv less than 24hrs old - updated at: %s",
            time.ctime(bills_age),
        )


# helis_dict = {}


# # print(bills.text)

# opsread = csv.DictReader(bills.text.splitlines())
# for row in opsread:
#     # print(row)
#     helis_dict[row["hex"].lower()] = row["type"]
#     logger.debug("Loaded %s :: %s", row["hex"].lower(), row["type"])

# print(helis_dict)


# print(cr)
# print(json.dumps(bills.text))
