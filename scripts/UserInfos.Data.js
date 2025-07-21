UserInfos.prototype.addUser = function(data) {
    var collection = firebase.firestore().collection('restaurant');
    return collection.add(data)
}