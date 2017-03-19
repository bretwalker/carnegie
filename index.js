var Alexa = require('alexa-sdk');
var mysql = require('mysql');
var step = require('step');

var connection = mysql.createConnection(
    {
      host     : 'civicdata.crogewynsqom.us-east-1.rds.amazonaws.com',
      user     : 'admin',
      password : 'bloodsweatandtears',
      database : 'louisvilleky',
    }
);

const SKILL_NAME = "Louisville";
// TODO could be a DB lookup
const MONTH_MAP = new Map();

var handlers = {
    "GetRobberies": function() {
    	var month = this.event.request.intent.slots.Month.value.toLowerCase();
    	var neighborhood = this.event.request.intent.slots.Area.value.toLowerCase();
    	var alexa = this;
    	var robberyCount = -1;

		step (
			function getRobberyCount() {
				var query = " select count(CRIME_TYPE) as cnt " +
							" from crimeData " +
							" where CRIME_TYPE = 'robbery' " +
							" and ZIP_CODE in (select zip from zipCodeLookup where neighborhood = ? ) " +
							" and " + buildDateBetweenClause(month);

				console.log(query);
				connection.query(query, [neighborhood], this);		    
		    },
			function finish(err, rows, fields) {
				var speechOutput;

				if(err) {
					speechOutput = "I'm having trouble getting that information. Please try again later.";
					console.log(err);
				} else {
					robberyCount = rows[0].cnt;

					if(robberyCount == 0) {
						step (
							// if robberyCount = 0 we want to check that we have zip entries for the requested neighborhood.
							// it's possible that the user supplied something for which we haven't accounted.
							function getNeighborhoodCount() {
								var query = " select count(zip) as cnt from zipCodeLookup where neighborhood = ? ";
								connection.query(query, [neighborhood], this);
							},
							function finish(err, rows, fields) {
								var neighborhoodCount = -1;
								
								if(err) {
									console.log(err);
								} else {
									neighborhoodCount = rows[0].cnt;

									if(neighborhoodCount > 0) {
					        			speechOutput = "There were " + robberyCount + " robberies reported in " + neighborhood + " in " + month + ".";
						        	} else {
						        		speechOutput = "I don't have any zip codes configured for " + neighborhood + ".";
						        		console.log("No zips configured for " + neighborhood);
						        	}
								}

								// commented out these connection.end() statements. 
								// they were causing issues during testing where every other test would fail.
								// bonus is that requests respond faster but need to figure out how to check # of open DB connections on RDS.
								//connection.end();
								alexa.emit(':tellWithCard', speechOutput, SKILL_NAME, speechOutput);
							}
						);
					} else {
						speechOutput = "There were " + robberyCount + " robberies reported in " + neighborhood + " in " + month + ".";
						//connection.end();
						alexa.emit(':tellWithCard', speechOutput, SKILL_NAME, speechOutput);
					}
			    }
			}
		);
    },
    "GetRobberiesThisYearInNeighborhood": function() {
    	var neighborhood = this.event.request.intent.slots.Area.value.toLowerCase();
    	var count = -1;

		
		
        this.emit(':tellWithCard', speechOutput, SKILL_NAME, speechOutput);
    },
    "GetRobberiesThisWeek": function() {
    	var neighborhood = this.event.request.intent.slots.Area.value.toLowerCase();
    	var count = -1;

		if(neighborhood == "the highlands") {
			count = 20;
		} else if(neighborhood == "crescent hill") {
			count = 6;
		}
        
        if(count > -1) {
        	speechOutput = "There were " + count + " robberies reported this month in " + neighborhood + ".";
        } else {
        	speechOutput = "I don't have that information at this time."
        }
		
        this.emit(':tellWithCard', speechOutput, SKILL_NAME, speechOutput);
    },

    "AMAZON.HelpIntent": function() {
        var speechOutput = "";
        speechOutput += "Here are some things you can say: ";
        speechOutput += "How many robberies occurred in January in The Highlands?";
        speechOutput += "You can also say stop if you're done. ";
        speechOutput += "So how can I help?";
        this.emit(':ask', speechOutput, speechOutput);
    },

    "AMAZON.StopIntent": function() {
        var speechOutput = "Goodbye";
        this.emit(':tell', speechOutput);
    },

    "AMAZON.CancelIntent": function() {
        var speechOutput = "Goodbye";
        this.emit(':tell', speechOutput);
    },

    "LaunchRequest": function() {
        var speechText = "";
        speechText += "Welcome to " + SKILL_NAME + ".  ";
        speechText += "You can ask questions about the number of robberies in a certain neighborhood.";
        var repromptText = "For instructions on what you can say, please say help me.";
        this.emit(':ask', speechText, repromptText);
    }
};

function init() {
	MONTH_MAP.set("january", " '{year}-01-01 00:00:00' and '{year}-01-31 23:59:59' ");
	MONTH_MAP.set("february", " '{year}-02-01 00:00:00' and '{year}-02-28 23:59:59' ");
	MONTH_MAP.set("march", " '{year}-03-01 00:00:00' and '{year}-03-31 23:59:59' ");
	MONTH_MAP.set("april", " '{year}-04-01 00:00:00' and '{year}-04-30 23:59:59' ");
	MONTH_MAP.set("may", " '{year}-05-01 00:00:00' and '{year}-05-31 23:59:59' ");
	MONTH_MAP.set("june", " '{year}-06-01 00:00:00' and '{year}-06-30 23:59:59' ");
	MONTH_MAP.set("july", " '{year}-07-01 00:00:00' and '{year}-07-31 23:59:59' ");
	MONTH_MAP.set("august", " '{year}-08-01 00:00:00' and '{year}-08-31 23:59:59' ");
	MONTH_MAP.set("september", " '{year}-09-01 00:00:00' and '{year}-09-30 23:59:59' ");
	MONTH_MAP.set("october", " '{year}-10-01 00:00:00' and '{year}-10-31 23:59:59' ");
	MONTH_MAP.set("november", " '{year}-11-01 00:00:00' and '{year}-11-30 23:59:59' ");
	MONTH_MAP.set("december", " '{year}-12-01 00:00:00' and '{year}-12-31 23:59:59' ");
}

// NOT USED. Functionality moved in-line above 
function getNeighborhoodCount(neighborhood) {
	step (
		function start() {
			var query = " select count(zip) as cnt from zipCodeLookup where neighborhood = ? ";
			console.log('executing zipCodeLookup query... ' + neighborhood);
			connection.query(query, [neighborhood], this);
	    },
		function finish(err, rows, fields) {
			console.log('inside finish');
			if(err) {
				console.log(err);
				return -1;
			} else {
				console.log("getNeighborhoodCount cnt: " + rows[0].cnt);
				return rows[0].cnt;
		    }
		}
	);
}

function buildDateBetweenClause(month) {
	var year = new Date().getFullYear();
	var mapVal = MONTH_MAP.get(month);
	var betweenClause = ' 1 = 1 ';

	if(typeof mapVal !== 'undefined' && mapVal) {
		betweenClause = ' (DATE_OCCURED between ' + mapVal.replace(new RegExp('{year}', 'g'), year) + ') ';
	} else {
		console.log("Month value [" + month + "] not found in MONTH_MAP.");
	}

	return betweenClause;
}

exports.handler = function(event, context) {
	init();

    var alexa = Alexa.handler(event, context);

    alexa.appId = "amzn1.ask.skill.f1666054-3195-4e05-9e59-d32d227c9c87";
    alexa.registerHandlers(handlers);
    alexa.execute();
};