import pymongo

mapFunction = """function() {
					var ids = [];
					ids.push(this.docID)
					for (var i in this.words){
						var key = this.words[i].word;
						var value = { 'ids': ids};
						emit(key, value);
					}
				}"""

reduceFunction = """function(key, values) {
					var result = {'ids': []};
					values.forEach(function (v) {
						result.ids = v.ids.concat(result.ids)
					});
					return result;
				};"""

functionCreate = """function(){
				var items = db.temp_collection.find().addOption(DBQuery.Option.noTimeout);
				while(items.hasNext()){
					var item = items.next();
					doc = {word: item._id, createdAt: new Date(), docIDs: item.value.ids};
					db.inverted_index.insert(doc);
				}
			}"""

functionUpdate = """function(){
				var items = db.temp_collection.find().addOption(DBQuery.Option.noTimeout);
				while(items.hasNext()){
					var item = items.next();
					var wordID = item._id;					
					var exists = db.inverted_index.findOne({word: wordID}, {docIDs: 1, _id: 0});
					if (exists){
							var docIDs = exists.docIDs;		
							docIDs = docIDs.concat(item.value.ids);
							db.inverted_index.update({word: wordID}, {$set: {docIDs: docids_vec}});
					}else{
						doc = {word: wordID, createdAt: new Date(), docIDs: item.value.ids};
						db.inverted_index.insert(doc);
					}
				}
			}"""

functionDelete = """function (){
						var words = db.inverted_index.find({},{_id: 0, word: 1}).addOption(DBQuery.Option.noTimeout);
						while(words.hasNext()){
							var word = words.next();
							var n = db.inverted_index.aggregate([
											{$match: {word: word.word}},
											{$project: { '_id': 0, noWords: { $size: "$docIDs" }}}
										]);
							var noWords = 0;
							while(n.hasNext()){ 
								var v = n.next(); 
								noWords = v.noWords; 
							}
							if (noWords == 0){
								// delete words that have no related document
								db.inverted_index.remove({word: word.word});
							}
						}
					}"""

class InvertedIndex:
	def __init__(self, dbname):
		client = pymongo.MongoClient()
		self.db = client[dbname]


	def createIndex(self, query=None):
		self.db.inverted_index.drop();
		if query:
			self.db.words.map_reduce(mapFunction, reduceFunction, "temp_collection", query = query)
		else:
			self.db.words.map_reduce(mapFunction, reduceFunction, "temp_collection")
		self.db.eval(functionCreate)
		self.db.inverted_index.ensure_index("word")
		self.db.temp_collection.drop()

	def updateIndex(self, startDate):
		query = query = {"createdAt": {"$gt": startDate } }
		self.db.words.map_reduce(mapFunction, reduceFunction, "temp_collection", query = query)		
		self.db.eval(functionCreate, {'startDate': startDate})
		self.db.temp_collection.drop()

	#docIDs - list of documents
	def deleteIndex(self, docIDs):
		for docID in docIDs:
			self.db.inverted_index.update({ }, { "$pull": { "docIDs" : docID } },  multi=True)
		self.db.eval(functionDelete, {'docIDs': docIDs})
