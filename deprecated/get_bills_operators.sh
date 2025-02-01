#!/bin/sh

DATELINE=`date '+%Y%m%d%H%M%S'`


cp bills_operators.csv bills_operators_${DATELINE}.csv

wget  "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv" -O "bills_operators.csv"


diff bills_operators.csv bills_operators_${DATELINE}.csv
