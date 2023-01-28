#start by running
sudo apt-get update

#the following is required for FR24 feeder images
sudo apt-get install python3-pip

#required for ALL
pip3 install pymongo

#get the script and our helicopter database:
curl -LJO https://raw.githubusercontent.com/LoganSound/CopterFeeder/main/feed_copterspotter.py
wget "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv" -O "/home/pi/bills_operators.csv"

#add your credentials and feeder type to the top of the file:
nano feed_copterspotter.py

#make it executable
chmod a+x feed_copterspotter.py

#type:
crontab -e

#and add the following lines:
* * * * * python /home/pi/feed_copterspotter.py >> copterspotter.log 2>&1
0 0 * * * wget "https://docs.google.com/spreadsheets/d/e/2PACX-1vSEyC5hDeD-ag4hC1Zy9m-GT8kqO4f35Bj9omB0v2LmV1FrH1aHGc-i0fOXoXmZvzGTccW609Yv3iUs/pub?gid=0&single=true&output=csv" -O "/home/pi/bills_operators.csv"

#DONE
#you can TEST it by typing
python3 feed_copterspotter.py

# when an identifyied helicopter is nearby it should return something like:
1674864903.049228 A139 TRP7 450 600 97.22 38.909385,-76.845398 5107
#if you consistently see "None" or "Null" we may need to tweak your variables
