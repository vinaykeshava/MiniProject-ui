import json
import os
from flask import Flask, request, jsonify,render_template,redirect,url_for,flash,session,logging
import pymongo
from datetime import timedelta
import face_recognition
import pyrebase
import requests
import shutil
from dotenv import load_dotenv

app = Flask(__name__)


load_dotenv()
config = {
    # get .env varables
    "apiKey": os.getenv("apiKey"),
    "authDomain": os.getenv('authDomain'),
    "projectId": os.getenv('projectId'),
    "storageBucket": os.getenv('storageBucket'),
    "messagingSenderId": os.getenv('messagingSenderId'),
    "appId": os.getenv('appId'),
    "measurementId": os.getenv('measurementId'),
    "serviceAccount": "./serviceAccount.json",
    "databaseURL": os.getenv('databaseURL')
}

try:
    firebase = pyrebase.initialize_app(config)
    storage = firebase.storage()
    print("Firebase initialized")
except:
    print("Error initializing Firebase")



MONGODB_CONNECT = os.getenv("MONGODB_CONNECT")
LOCALDB = os.getenv("LOCALDB")
SECRETE_KEY= os.getenv("SECRETE_KEY")
app.config['SECRET_KEY'] = SECRETE_KEY
app.permanent_session_lifetime = timedelta(days=5)


try:
    mongoclient = pymongo.MongoClient(MONGODB_CONNECT)
    print("Database connected")
except pymongo.errors.ConnectionFailure as e:
    print("Could not connect to MongoDB: %s" % e)
    print("Error connecting to database")
    exit()

crimeDeteUsers = mongoclient.crimeDeteUsers


@app.route('/')
@app.route('/home')
def home():
    if "user" in session:
        return render_template('main.html', data={"l":["database","Logout"]})
    return render_template('main.html', data={"l":["Login","SignUp"]})

@app.route("/SignUp", methods=['GET', 'POST'])
def register():
    if request.method == "GET":
        return render_template('register.html', data={"l":["Login","SignUp"]})
    else:
        data = request.get_json()
        if data["username"] == "" or data["password"] == "":
            return jsonify({"status": "error", "msg": "Please fill all the fields"})
        if crimeDeteUsers["users"].find_one({"username": data["username"]}):
            return jsonify({"status": "error", "msg": "Username already exists"})
        crimeDeteUsers["users"].insert_one(data)
        return jsonify({"status":"success","msg": "User registered successfully"})



@app.route("/Login", methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        if "user" in session:
            return redirect(url_for("home"))
        return render_template('login.html', data={"l":["Login","SignUp"]})
    else:
        data = request.get_json()
        print(data)
        user = crimeDeteUsers["users"].find_one({"email":data["email"]})
        if user:
            if user["password"] == data["password"]:
                session["user"] = user['username']
                return jsonify({"status":"success","msg": "User logged in successfully"})
            else:
                return jsonify({"status":"error","msg": "Invalid password"})
        else:
            return jsonify({"status":"error","msg": "Invalid email"})


@app.route('/database',methods=['GET', 'POST'])
def database():
    if "user" in session:
        if request.method == "GET":
            imgUrlList = []
            result = crimeDeteUsers["images"].find({"username":session["user"]})
            for i in result:
                imgUrlList.append({"url": i["imgUrl"], "filename": i["filename"]})
            return render_template('database.html', data={"l":["database","Logout"],
                                                         "imgUrlList": imgUrlList})
        else:
            return jsonify({"status":"error","msg": "You are not authorized to access this page"})
    else:
        return redirect(url_for("home"))


@app.route('/getInfo',methods=['GET', 'POST'])
def getInfo():
    if "user" in session:
        if request.method == "POST":
            data = request.get_json()
            r = crimeDeteUsers["images"].find_one({"filename": data["filename"]})
            return jsonify({"status": "success", "msg": str(r)})


@app.route("/getImgInfo/<file>",methods=['GET', 'POST'])
def getImgInfo(file):
    if "user" in session:
        if request.method == "GET":
            r = crimeDeteUsers["images"].find_one({"filename": file})
            return render_template('singleImg.html', data={"l":["database","Logout"],"imgdata":r })
            


@app.route("/Logout", methods=['GET', 'POST'])
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))




@app.route('/compareFaces', methods=['POST','GET'])
def compareFaces():
    if request.method == 'POST':
        data = request.get_json()
        filename = data['filename']
        img1url = crimeDeteUsers["images"].find_one({"filename": filename})["imgUrl"]
        try:
            storage.child(filename).download(filename,'./images/'+filename)
            print("Image downloaded")
            # res = requests.get(img1url, stream=True)
            # if res.status_code == 200:
            #     with open("./images/"+filename,'wb') as f:
            #         shutil.copyfileobj(res.raw, f)
            #         print('Image sucessfully Downloaded')
            #     f.close()
        except:
            return jsonify({"status": "error", "msg": "Error downloading image"})
        
        imgNameList = []
        r = crimeDeteUsers["images"].find()
        for i in r:
            imgNameList.append({"filename":i["filename"],"imgUrl":i["imgUrl"]})
        img1 = face_recognition.load_image_file("./images/"+filename)
        img1encoding = face_recognition.face_encodings(img1)
        for i in imgNameList:
            if i['imgUrl'] != img1url:
                try:
                    storage.child(i['filename']).download(i['filename'],'./images/'+i['filename'])
                    print("other Image downloaded")
                    # res = requests.get(i['imgUrl'], stream=True)
                    # if res.status_code == 200:
                    #     with open("./images/"+i['filename'],'wb') as file:
                    #         shutil.copyfileobj(res.raw, file)
                    #     file.close()
                    # else:                            
                    #     print('Image not found')
                except:
                    print("Error downloading image")

                # img2 = cv2.imread("./images/"+i['filename'])
                img2 = face_recognition.load_image_file("./images/"+i['filename'])
                img2encoding = face_recognition.face_encodings(img2)
                for i in img1encoding:
                    for j in img2encoding:
                        result = face_recognition.compare_faces([i], j)
                        print(result[0])
                        if result[0]:
                            for i in os.listdir("./images/"):
                                os.remove("./images/"+i)
                            return jsonify({"status": "success", "msg": "Face matched"})    
        for i in os.listdir("./images/"):
            os.remove("./images/"+i)
        return jsonify({"status": "error", "msg": "Face not matched"})
    return jsonify({"status": "success","msg": "Face detected"})


@app.route("/loginFromExe",methods=["POST","GET"])
def loginFromExe():
    if request.method == "POST":
        data = request.get_json()
        user = crimeDeteUsers["users"].find_one({"username":data["username"]})
        if user:
            if user["password"] == data["password"]:
                return jsonify({"status": "success","msg": "Login successful"})
            else:
                return jsonify({"status": "failure","msg": "Invalid password"})
        else:
            return jsonify({"status": "failure","msg": "Invalid username"})
    else:
        return jsonify({"status": "failure","msg": "No data received"})



@app.route("/imageUpload",methods=["POST","GET"])
def imageUpload():
    if request.method == "POST":
        data = request.files['json']
        data = json.loads(data.read())
        file = request.files['media']
        file.save(file.filename)
        storage.child(file.filename).put(file.filename)
        url = storage.child(file.filename).get_url(None)
        d = {
        'filename': data['name'],
        'username': data['username'],
        'camara': data['camara'],
        'date': data['date'],
        'time': data['time'],
        'imgUrl': url
        }
        crimeDeteUsers["images"].insert_one(d)
        os.remove(file.filename)
        # print(file)
        return jsonify({"status": "success","msg": "Image uploaded successfully"})

if __name__ == '__main__':
    app.run(debug=True)
