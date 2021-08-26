from flask import Flask, render_template, request, session, jsonify
from flaskext.mysql import MySQL
import os, base64
import re
from werkzeug.utils import secure_filename
import boto3
from flask_mail import Mail, Message
from itsdangerous import URLSafeSerializer


S3_BUCKET_NAME='galleryf'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

s3_client = boto3.client(
    's3', 
    aws_access_key_id="AKIAVYROQDADRXQKOUXT", 
    aws_secret_access_key= "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",
)

app = Flask(__name__, template_folder='templates')
db = MySQL()

app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = '1903Lara*'
app.config['MYSQL_DATABASE_DB'] = 'gallery'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['MYSQL_DATABASE_PORT'] = 3306
db.init_app(app)

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

conn = db.connect()
cursor = conn.cursor()

@app.route('/', methods=['POST', 'GET', 'DELETE'])
def home():
    query = 'SELECT photo_id, data, CAPTION FROM PHOTOS ORDER BY photo_id DESC LIMIT 100'
    cursor.execute(query)
    all_photos = []
    for item in cursor:
        img = ''.join(list(str(item[1]))[2:-1])
        all_photos.append([item[0], img, item[2]])
        contents = show_image(S3_BUCKET_NAME)

    return render_template('index.html', token="", photos=all_photos)

def show_image(bucket):
    s3_client = boto3.client('s3')
    public_urls = []
    try:
        for item in s3_client.list_objects(Bucket=bucket)['Contents']:
            presigned_url = s3_client.generate_presigned_url('get_object', Params = {'Bucket': bucket, 'Key': item['Key']}, ExpiresIn = 100)
            public_urls.append(presigned_url)
    except Exception as e:
        pass
    return public_urls

@app.route('/login_page', methods=['POST', 'GET', 'DELETE'])
def login_page(message='Please Log In'):
    return render_template('login_page.html', message=message)

@app.route('/signup_page', methods=['POST', 'GET', 'DELETE'])
def signup_page(message="Complete the form to sign up"):
    return render_template('signup_page.html', message=message)

@app.route('/signup', methods=['POST', 'GET', 'DELETE'])
def signup():

    result = request.form
    if result['password1'] != result['password2']:
        return signup_page("Password Mismatch")

    email = result['email']
    if email == 'anon@anon':
        return signup_page("This email is invalid")

    if result['first_name'] == 'anon' or result['last_name'] == 'anon':
        return signup_page("Your name cannot be anon")

    query = 'SELECT EMAIL FROM USERS'
    cursor.execute(query)
    for item in cursor:
        if item[0] == email:
            return login_page("You may already have an account - please log in")
        if item[0] == email.lower():
            return signup_page("Please pay attention to upper and lower case in your email")

    query = 'INSERT INTO USERS(EMAIL, PASSWORD, first_name, ' \
            'last_name) VALUES (%s, %s, %s, %s)'

    try:
        cursor.execute(query,
                   (result['email'], result['password1'], result['first_name'], result['last_name']))
    except:
        return signup_page("Oops, something went wrong - please try again")

    conn.commit()

    query = 'SELECT user_id, EMAIL, first_name FROM USERS'
    cursor.execute(query)
    for item in cursor:
        if email == item[1]:
            userid = item[0]
            my_name = item[2]
            break

    session['userid'] = userid
    session['my_name'] = my_name
    session['loggedin'] = True
    return view_profile(id=userid)

@app.route('/login', methods=['POST', 'GET', 'DELETE'])
def login():

    result = request.form
    email = result['email']
    password = result['password']

    query = 'SELECT EMAIL, PASSWORD, user_id, first_name FROM USERS'
    cursor.execute(query)
    if cursor.rowcount == 0:
        return signup_page("No Account with this email and password, would you like to create an account?")

    for item in cursor:
        if item[0] == email and email != 'anon@anon':
            if item[1] == password:
                session['userid'] = item[2]
                session['my_name'] = item[3]
                session['loggedin'] = True
                return view_profile(id=item[2])
            else:
                return login_page('Wrong Password')

    return signup_page("No Account with this email and password, would you like to create an account?")

@app.route('/logout', methods=['POST', 'GET', 'DELETE'])
def logout():
    session.clear()
    session['loggedin'] = False
    return home()

@app.route('/view_profile/<id>', methods=['POST', 'GET', 'DELETE'])
def view_profile(id):

    query = 'SELECT user_id, first_name FROM USERS'
    cursor.execute(query)
    for item in cursor:
        if int(id) == int(item[0]):
            person_name = item[1]

    query = 'SELECT album_id, user_id FROM ALBUMS ORDER BY album_id DESC'
    cursor.execute(query)
    all_albums = []
    for item in cursor:
        if int(item[1]) == int(id):
            all_albums.append(int(item[0]))

    query = 'SELECT photo_id, DATA, CAPTION, album_id FROM PHOTOS ORDER BY photo_id DESC LIMIT 100'
    cursor.execute(query)
    all_photos = []
    user_photos = []
    for item in cursor:
        img = ''.join(list(str(item[1]))[2:-1])
        all_photos.append([item[0], img, item[2]])
        if int(item[3]) in all_albums:
            user_photos.append([item[0], img, item[2]])

    if session.get('loggedin', None):

        userid = session.get('userid', None)
        my_name = session.get('my_name', None)

        if int(userid) == int(id):
            return render_template('profile.html', name=person_name, username=my_name,
                                   loggedin=True,
                                   myprofile=True, userid=userid, id=id, photos=all_photos)

        query = 'SELECT user_id1, user_id2 FROM FRIENDSHIP'
        cursor.execute(query)
        all_friends = []
        for item in cursor:
            if int(id) == int(item[0]):
                all_friends.append(int(item[1]))
            elif int(id) == int(item[1]):
                all_friends.append(int(item[0]))

        if userid in all_friends:
            friends = True
        else:
            friends = False

        return render_template('profile.html', name=person_name, username=my_name, loggedin=True,
                               myprofile=False, userid=userid, id=id, photos=all_photos, user_photos=user_photos, friends=friends)

    return render_template('profile.html', name=person_name, loggedin=False, id=id, user_photos=user_photos)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['POST', 'GET', 'DELETE'])
def upload():
    userid = session.get('userid', None)
    my_name = session.get('my_name', None)
    return render_template('upload.html', username=my_name, userid=userid)


@app.route('/create_album', methods=['POST', 'GET', 'DELETE'])
def create_album():

    userid = session.get('userid', None)
    my_name = session.get('my_name', None)

    result = request.form
    query = 'INSERT INTO ALBUMS(user_id, album_name) VALUES (%s, %s)'

    cursor.execute(query, (userid, result['album']))
    conn.commit()
    album_id = cursor.lastrowid

    return render_template('upload_photo.html', album_id=album_id, username=my_name, userid=userid)



@app.route('/upload_photo/<album_id>', methods=['POST', 'GET', 'DELETE'])
def upload_photo(album_id):

    userid = session.get('userid', None)
    my_name = session.get('my_name', None)

    if request.method == 'POST':
        cap = request.form['caption']
        hashtags = re.findall(r'\B(\#[a-zA-Z]+\b)(?!;)', cap)

        query1 = 'INSERT INTO ASSOCIATE(photo_id, HASHTAG) VALUES (%s, %s)'
        query2 = 'INSERT INTO TAG(HASHTAG) VALUES (%s)'
        query3 = 'SELECT * FROM TAG'

        for tag in hashtags:
            if len(tag) < 40:
                t = ''.join(list(tag)[1:])
                cap = re.sub(tag, "<a href=\"/view_tag/" + t + "\") }}\"> " + tag + " </a>", cap)

        query = 'INSERT INTO PHOTOS(album_id, DATA, CAPTION) VALUES (%s, %s, %s)'
        image = request.files['img']

        cursor.execute(query, (album_id, base64.standard_b64encode(image.read()), cap))
        conn.commit()
        
        if image:
            filename = secure_filename(image.filename)
            image.save(filename)
            s3_client.upload_file(
                Bucket = S3_BUCKET_NAME,
                Filename=filename,
                Key = filename
            )

        photo_id = cursor.lastrowid

        cursor.execute(query3)

        all_tags = []
        for item in cursor:
            all_tags.append(item[0])

        for tag in hashtags:
            if tag not in all_tags and len(tag) < 40:
                cursor.execute(query2, tag)
                conn.commit()
                all_tags.append(tag)

        for tag in hashtags:
            if len(tag) < 40:
                cursor.execute(query1, (photo_id, tag))
                conn.commit()
                
        return render_template('upload_photo.html', album_id=album_id, username=my_name, userid=userid)

    return render_template('upload_photo.html', album_id=album_id, username=my_name, userid=userid)

@app.route('/view_all_albums/<uploader_id>', methods=['POST', 'GET', 'DELETE'])
def view_all_albums(uploader_id):

    query = 'SELECT album_id, album_name, user_id FROM ALBUMS ORDER BY album_id DESC'
    cursor.execute(query)
    all_albums = []
    for item in cursor:
        if int(item[2]) == int(uploader_id):
            all_albums.append([item[0], item[1]])

    query = 'SELECT user_id, first_name FROM USERS'
    cursor.execute(query)
    for item in cursor:
        if int(item[0]) == int(uploader_id):
            uploader_name = item[1]
            break

    if session.get('loggedin', None):
        userid = session.get('userid', None)
        my_name = session.get('my_name', None)

        return render_template('view_all_albums.html', username=my_name, userid=int(userid), uploader_name=uploader_name,
                               all_albums=all_albums, loggedin=True, uploader_id=int(uploader_id))

    return render_template('view_all_albums.html', uploader_name=uploader_name,
                           all_albums=all_albums, loggedin=False, uploader_id=uploader_id)


@app.route('/view_album_content/<album_id>', methods=['POST', 'GET', 'DELETE'])
def view_album_content(album_id):

    query = 'SELECT album_id, album_name, user_id FROM ALBUMS'
    cursor.execute(query)
    for item in cursor:
        if int(item[0]) == int(album_id):
            album_name = item[1]
            uploader_id = item[2]
            break

    query = 'SELECT first_name, user_id FROM USERS'
    cursor.execute(query)
    for item in cursor:
        if int(item[1]) == int(uploader_id):
            uploader_name = item[0]
            break

    query = 'SELECT photo_id, DATA, CAPTION, album_id FROM PHOTOS'
    cursor.execute(query)
    all_photos = []
    for item in cursor:
        if int(item[3]) == int(album_id):
            img = ''.join(list(str(item[1]))[2:-1])
            all_photos.append([item[0], img, item[2]])

    if session.get('loggedin'):

        userid = session.get('userid', None)
        my_name = session.get('my_name', None)
        return render_template('view_album_content.html', username=my_name, uploader_name=uploader_name, loggedin=True,
                               userid=int(userid), uploader_id=int(uploader_id), photos=all_photos, album_id=album_id,
                               album_name=album_name)

    else:
        return render_template('view_album_content.html', uploader_name=uploader_name, loggedin=False,
                               uploader_id=uploader_id, photos=all_photos, album_id=album_id, album_name=album_name)

@app.route('/view_photo/<photo_id>', methods=['POST', 'GET', 'DELETE'])
def view_photo(photo_id):

    query = 'SELECT photo_id, DATA, CAPTION, album_id FROM PHOTOS'
    cursor.execute(query)
    for item in cursor:
        if int(item[0]) == int(photo_id):
            img = ''.join(list(str(item[1]))[2:-1])
            photo = [img, item[2], photo_id]
            album_id = int(item[3])

    query = 'SELECT photo_id, comment_id, CONTENT, user_id FROM COMMENTS'
    cursor.execute(query)
    comments = []
    for item in cursor:
        if int(item[0]) == int(photo_id):
            comments.append([int(item[3]), item[2], item[1]])

    commenterids = [x[0] for x in comments]
    all_comments = []

    query = 'SELECT user_id, first_name FROM USERS'
    cursor.execute(query)
    all_commenters = []
    for item in cursor:
        if int(item[0]) in commenterids:
            all_commenters.append([int(item[0]), item[1]])

    for i in range(len(comments)):
        for j in range(len(all_commenters)):
            if comments[i][0] == all_commenters[j][0]:
                all_comments.append([comments[i][0], all_commenters[j][1], comments[i][1], int(comments[i][2])])

    query = 'SELECT album_name, album_id, user_id FROM ALBUMS'
    cursor.execute(query)
    for item in cursor:
        if int(item[1]) == int(album_id):
            album_name = item[0]
            uploader_id = item[2]
            break

    query = 'SELECT first_name, user_id FROM USERS'
    cursor.execute(query)
    for item in cursor:
        if int(item[1]) == int(uploader_id):
            uploader_name = item[0]
            break

    query = 'SELECT user_id, photo_id FROM LIKETABLE'
    cursor.execute(query)
    likers = []
    for item in cursor:
        if int(item[1]) == int(photo_id):
            likers.append(int(item[0]))

    query = 'SELECT first_name, user_id FROM USERS'
    cursor.execute(query)
    likedby = []
    for item in cursor:
        if int(item[1]) in likers:
            likedby.append([item[1], item[0]])

    query = 'SELECT HASHTAG, photo_id FROM ASSOCIATE'
    cursor.execute(query)
    tagged_with = []
    for item in cursor:
        if int(item[1]) == int(photo_id):
            tagged_with.append(item[0])

    if session.get('loggedin'):

        userid = session.get('userid', None)
        my_name = session.get('my_name', None)

        if userid in likers:
            liked = True
        else:
            liked = False

        if int(userid) == int(uploader_id):
            mypic = True
        else:
            mypic = False

        return render_template('view_photo.html', username=my_name, uploader_name=uploader_name, loggedin=True,
                               liked=liked, likedby=likedby, like_num=len(likedby), userid=int(userid),
                               uploader_id=int(uploader_id), photo=photo, album_id=album_id, album_name=album_name,
                               comments=all_comments, mypic=mypic)

    else:
        return render_template('view_photo.html', uploader_name=uploader_name, loggedin=False, likedby=likedby, like_num=len(likedby),
                               uploader_id=uploader_id, photo=photo, album_id=album_id, album_name=album_name,
                               comments=all_comments)

@app.route('/comment/<photo_id>', methods=['POST', 'GET', 'DELETE'])
def comment(photo_id):

    comm = request.form['comment']
    hashtags = re.findall(r'\B(\#[a-zA-Z]+\b)(?!;)', comm)

    query1 = 'INSERT INTO ASSOCIATE(photo_id, HASHTAG) VALUES (%s, %s)'
    query2 = 'INSERT INTO TAG(HASHTAG) VALUES (%s)'
    query3 = 'SELECT * FROM TAG'

    for tag in hashtags:
        if len(tag)<40:
            t = ''.join(list(tag)[1:])
            comm = re.sub(tag, "<a href=\"/view_tag/"+t+"\") }}\"> "+tag+" </a>", comm)

    cursor.execute(query3)

    all_tags = []
    for item in cursor:
        all_tags.append(item[0])

    for tag in hashtags:
        if (tag not in all_tags) and len(tag)<40:
            cursor.execute(query2, tag)
            conn.commit()
            all_tags.append(tag)

    for tag in hashtags:
        if len(tag) < 40:
            try:
                cursor.execute(query1, (photo_id, tag))
            except:
                break
            conn.commit()

    if session.get('loggedin', None):

        userid = session.get('userid', None)

        query = 'INSERT INTO COMMENTS(photo_id, CONTENT, user_id) VALUES (%s, %s, %s)'

        cursor.execute(query, (photo_id, comm, userid))
        conn.commit()

        return view_photo(photo_id=photo_id)

    query = 'SELECT user_id, EMAIL, first_name FROM USERS WHERE EMAIL=%s'
    cursor.execute(query, "anon@anon")

    anon_user = []

    for item in cursor:
        anon_user = [item[0], item[2]]

    if anon_user:

        userid = anon_user[0]
        query = 'INSERT INTO COMMENTS(photo_id, CONTENT, user_id) VALUES (%s, %s, %s)'

        cursor.execute(query, (photo_id, comm, userid))
        conn.commit()

        return view_photo(photo_id=photo_id)

    query = 'INSERT INTO USERS(EMAIL, PASSWORD, first_name, ' \
            'last_name) VALUES (%s, %s, %s, %s)'
    cursor.execute(query, ('anon@anon', 'anon123', 'anon', 'anon', '1900-01-01', 'anon', 'O'))
    conn.commit()

    userid = cursor.lastrowid

    query = 'INSERT INTO COMMENTS(photo_id, CONTENT, user_id) VALUES (%s, %s, %s)'

    cursor.execute(query, (photo_id, comm, userid))
    conn.commit()

    return view_photo(photo_id=photo_id)

@app.route('/friend_add/<friend_id>', methods=['POST', 'GET', 'DELETE'])
def friend_add(friend_id):

    userid = session.get('userid', None)

    query = 'INSERT INTO FRIENDSHIP(user_id1, user_id2) VALUES (%s, %s)'
    cursor.execute(query, (userid, friend_id))
    conn.commit()

    return view_profile(friend_id)

@app.route('/view_friends/<id>', methods=['POST', 'GET', 'DELETE'])
def view_friends(id):

    query = 'SELECT user_id, first_name FROM USERS'
    cursor.execute(query)
    for item in cursor:
        if int(item[0]) == int(id):
            name = item[1]

    query = 'SELECT user_id1, user_id2 FROM FRIENDSHIP'
    cursor.execute(query)
    friends = []
    for item in cursor:
        if int(id) == int(item[0]):
            friends.append(int(item[1]))
        elif int(id) == int(item[1]):
            friends.append(int(item[0]))

    query = 'SELECT user_id, first_name FROM USERS'
    cursor.execute(query)
    all_friends = []
    for item in cursor:
        for fid in friends:
            if int(item[0]) == fid:
                all_friends.append([item[0], item[1]])

    if session.get('loggedin', None):

        userid = session.get('userid', None)
        my_name = session.get('my_name', None)

        recommended_friends = friend_recommendation(userid, friends)

        return render_template("view_friends.html", friends=all_friends, username=my_name, userid=int(userid),
                               name=name, id=int(id), loggedin=True, recommended_friends=recommended_friends)

    return render_template("view_friends.html", friends=all_friends, name=name, id=id,
                           loggedin=False)


@app.route('/like/<photo_id>', methods=['POST', 'GET', 'DELETE'])
def like(photo_id):

    userid = session.get('userid', None)
    query = 'INSERT INTO LIKETABLE(user_id, photo_id) VALUES (%s, %s)'
    cursor.execute(query, (userid, photo_id))
    conn.commit()

    return view_photo(photo_id)


@app.route('/view_my_tags/<id>', methods=['POST', 'GET', 'DELETE'])   #can use to see any person's tags later
def view_my_tags(id):

    query = 'SELECT user_id, first_name FROM USERS'
    cursor.execute(query)
    for item in cursor:
        if int(item[0]) == int(id):
            my_name = item[1]

    query = 'SELECT album_id, user_id FROM ALBUMS ORDER BY album_id DESC'
    cursor.execute(query)
    all_albums = []
    for item in cursor:
        if int(item[1]) == int(id):
            all_albums.append(int(item[0]))

    query = 'SELECT photo_id, album_id FROM PHOTOS ORDER BY photo_id DESC LIMIT 100'
    cursor.execute(query)
    user_photos = []
    for item in cursor:
        if int(item[1]) in all_albums:
            user_photos.append(item[0])


@app.route('/view_tag_content/<tag>', methods=['POST', 'GET', 'DELETE'])
def view_tag_content(tag):

    if tag[0] != '#':
        tag = '#'+tag

    query = 'SELECT photo_id, HASHTAG FROM ASSOCIATE'
    all_photoids = []
    cursor.execute(query)
    for item in cursor:
        if item[1] == tag:
            all_photoids.append(int(item[0]))

    userid = session.get('userid')
    my_name = session.get('my_name')
    query = 'SELECT album_id, user_id FROM ALBUMS ORDER BY album_id DESC'
    cursor.execute(query)
    all_albums = []
    for item in cursor:
        if int(item[1]) == int(userid):
            all_albums.append(int(item[0]))

    query = 'SELECT photo_id, album_id FROM PHOTOS ORDER BY photo_id DESC LIMIT 100'
    cursor.execute(query)
    user_photos = []
    for item in cursor:
        if int(item[1]) in all_albums:
            user_photos.append(int(item[0]))

    tag_content_id = [int(x) for x in all_photoids if x in user_photos]

    query = 'SELECT photo_id, DATA FROM PHOTOS'
    all_photos = []
    cursor.execute(query)
    for item in cursor:
        for photo in tag_content_id:
            if photo == int(item[0]):
                img = ''.join(list(str(item[1]))[2:-1])
                all_photos.append([item[0], img])


    return render_template('view_tag.html', tag=tag, photos=all_photos, loggedin=True,
                           userid=userid, username=my_name)


@app.route('/view_tag/<tag>', methods=['POST', 'GET', 'DELETE'])
def view_tag(tag):

    if tag[0] != '#':
        tag = '#'+tag

    query = 'SELECT photo_id, HASHTAG FROM ASSOCIATE'
    all_photoids = []
    cursor.execute(query)
    for item in cursor:
        if item[1] == tag:
            all_photoids.append(int(item[0]))

    query = 'SELECT photo_id, DATA FROM PHOTOS'
    all_photos = []
    cursor.execute(query)
    for item in cursor:
        for photo in all_photoids:
            if photo == int(item[0]):
                img = ''.join(list(str(item[1]))[2:-1])
                all_photos.append([item[0], img])

    if session.get('loggedin', None):

        return render_template('view_tag.html', tag=tag, photos=all_photos, loggedin=True,
                               userid=session.get('userid', None), username=session.get('my_name', None))

    return render_template('view_tag.html', tag=tag, photos=all_photos, loggedin=False)


@app.route('/delete_photo/<photo_id>', methods=['POST', 'GET', 'DELETE'])
def delete_photo(photo_id):

    userid = session.get('userid', None)

    query = 'DELETE FROM PHOTOS WHERE photo_id=%s'
    cursor.execute(query, photo_id)
    conn.commit()

    return view_profile(id=userid)

@app.route('/delete_comment/<comment_id>', methods=['POST', 'GET', 'DELETE'])
def delete_comment(comment_id):

    userid = session.get('userid', None)

    query= 'SELECT comment_id, CONTENT, photo_id FROM COMMENTS'
    cursor.execute(query)

    for item in cursor:
        if int(item[0]) == int(comment_id):
            comm = item[1]
            photo_id = item[2]
            break

    tags = re.findall(r'\B(\#[a-zA-Z]+\b)(?!;)', comm)

    query = 'DELETE FROM ASSOCIATE WHERE photo_id=%s AND HASHTAG=%s'
    for tag in tags:
        cursor.execute(query, (photo_id, tag))

    query = 'DELETE FROM COMMENTS WHERE comment_id=%s'
    cursor.execute(query, comment_id)
    conn.commit()

    return view_photo(photo_id=photo_id)

@app.route('/delete_album/<album_id>', methods=['POST', 'GET', 'DELETE'])
def delete_album(album_id):

    userid = session.get('userid', None)

    query = 'DELETE FROM ALBUMS WHERE album_id=%s'
    cursor.execute(query, album_id)
    conn.commit()

    return view_profile(id=userid)


@app.route('/unlike/<photo_id>', methods=['POST', 'GET', 'DELETE'])
def unlike(photo_id):

    userid = session.get('userid', None)

    query = 'DELETE FROM LIKETABLE WHERE photo_id=%s AND user_id=%s'
    cursor.execute(query, (photo_id, userid))
    conn.commit()

    return view_photo(photo_id=photo_id)


@app.route('/unfriend/<friend_id>', methods=['POST', 'GET', 'DELETE'])
def unfriend(friend_id):

    userid = session.get('userid', None)

    query = 'DELETE FROM FRIENDSHIP WHERE (user_id1=%s AND user_id2=%s) OR (user_id2=%s AND user_id1=%s)'
    cursor.execute(query, (friend_id, userid, friend_id, userid))
    conn.commit()

    return view_profile(id=friend_id)

@app.route('/all_users', methods=['POST', 'GET', 'DELETE'])
def all_users():
    query = 'SELECT user_id, first_name, last_name FROM USERS'
    cursor.execute(query)

    all_users = []
    for item in cursor:
        all_users.append([item[0], item[1]+' '+item[2]])

    if session.get('loggedin', None):
        userid = session.get('userid', None)
        my_name = session.get('my_name', None)


        return render_template('all_users.html', all_users=all_users, username=my_name, userid=userid, loggedin=True)

    return render_template('all_users.html', all_users=all_users)


@app.route('/top_users', methods=['POST', 'GET', 'DELETE'])
def top_users():

    query0 ='SELECT user_id, COUNT(*) AS Pscore ' \
            'FROM PHOTOS AS P JOIN ALBUMS AS A ON P.album_id = A.album_id ' \
            'GROUP BY user_id '

    query1 = 'SELECT user_id, COUNT(comment_id) AS Cscore FROM COMMENTS GROUP BY user_id'

    query2 = 'SELECT user_id FROM USERS'
    query3 = 'SELECT user_id FROM USERS WHERE EMAIL =%s'

    anon = -3
    cursor.execute(query3, 'anon@anon')
    for item in cursor:
        anon = int(item[0])
        break

    cursor.execute(query2)

    all_users = []
    for item in cursor:
        if int(item[0]) != anon:
            all_users.append(int(item[0]))

    cursor.execute(query0)

    top10id_photo = []
    for item in cursor:
        top10id_photo.append([int(item[0]), int(item[1])])

    only_ids_photo = [x[0] for x in top10id_photo]

    for user in all_users:
        if user not in only_ids_photo:
            top10id_photo.append([user, 0])

    cursor.execute(query1)

    top10id_comment = []
    for item in cursor:
        top10id_comment.append([int(item[0]), int(item[1])])

    only_ids_comment = [x[0] for x in top10id_comment]

    for user in all_users:
        if user not in only_ids_comment:
            top10id_comment.append([user, 0])

    top10id = [[x[0], x[1] + y[1]] for x in top10id_photo for y in top10id_comment if x[0] == y[0]]

    top10id = list(reversed(sorted(top10id, key=lambda x:x[1])))[:10]

    query = 'SELECT first_name, user_id FROM USERS WHERE user_id = %s'

    top10 = []
    for topid in top10id:
        cursor.execute(query, topid[0])
        for item in cursor:
            top10.append([item[1], item[0]])

    if session.get('loggedin', None):

        userid = session.get('userid', None)
        my_name = session.get('my_name', None)

        return render_template('top_users.html', top10=top10, userid=userid, username=my_name, loggedin=True)

    return render_template('top_users.html', top10=top10, loggedin=False)


@app.route('/top_tags', methods=['POST', 'GET', 'DELETE'])
def top_tags():

    query = 'SELECT COUNT(*) AS score, HASHTAG FROM ASSOCIATE GROUP BY HASHTAG ORDER BY score DESC LIMIT 10'
    cursor.execute(query)

    top10 = []
    for item in cursor:
        top10.append(item[1])

    if session.get('loggedin', None):

        userid = session.get('userid', None)
        my_name = session.get('my_name', None)

        return render_template('top_tags.html', top10=top10, userid=userid, username=my_name, loggedin=True)

    return render_template('top_tags.html', top10=top10, loggedin=False)


def photo_search(key_words):

    results = []

    query3 = "SELECT photo_id, HASHTAG FROM ASSOCIATE"
    cursor.execute(query3)

    photo_id_set = []
    id_tag = []

    for item in cursor:

        if int(item[0]) not in photo_id_set:
            id_tag.append([int(item[0]), item[1]])
            photo_id_set.append(int(item[0]))

        else:
            for i in range(len(id_tag)):
                if int(id_tag[i][0]) == int(item[0]):
                    id_tag[i].append(item[1])

    pid_sim = []
    for tag in id_tag:
        pid = int(tag[0])
        ptags = tag[1:]
        sim = compute_jaccard_index(set(key_words), set(ptags))

        pid_sim.append([pid, sim])

    rank = list(reversed(sorted(pid_sim, key=lambda x: x[1])))
    pids = [int(x[0]) for x in rank if x[1] > 0]

    query = 'SELECT photo_id, DATA, CAPTION, album_id FROM PHOTOS'
    cursor.execute(query)

    pic_and_data = []
    for item in cursor:
        img = ''.join(list(str(item[1]))[2:-1])
        pic_and_data.append([int(item[0]), img])

    for i in range(len(pids)):
        for j in range(len(pic_and_data)):
            if int(pids[i]) == int(pic_and_data[j][0]):
                results.append([pic_and_data[j][0], pic_and_data[j][1]])

    return results


@app.route('/search', methods=['POST', 'GET', 'DELETE'])
def search():

    results = []

    if request.method == 'POST':

        search_type = request.form['search_type']
        search_word = request.form['search_word']

        if search_type == "comment":

            hashtags = re.findall(r'\B(\#[a-zA-Z]+\b)(?!;)', search_word)

            for tag in hashtags:
                if len(tag) < 40:
                    t = ''.join(list(tag)[1:])
                    search_word = re.sub(tag, "<a href=\"/view_tag/" + t + "\") }}\"> " + tag + " </a>", search_word)

            query1 = 'SELECT user_id, CONTENT FROM COMMENTS'
            cursor.execute(query1)
            user = []
            for item in cursor:
                if item[1] == search_word:
                    user.append(int(item[0]))

            query2 = 'SELECT first_name, user_id FROM USERS'
            cursor.execute(query2)
            for item in cursor:
                if int(item[1]) in user:
                    results.append([item[1], item[0]])

            the_results = []
            all_ids = []
            for i in range(len(results)):
                count = 0
                for j in range(i, len(results)):
                    if results[i][0] == results[j][0]:
                        count += 1
                if results[i][0] not in all_ids:
                    all_ids.append(results[i][0])
                    the_results.append([results[i][0], results[i][1], count])

            results = list(reversed(sorted(the_results, key=lambda x: x[2])))

            if session.get('loggedin', None):

                userid = session.get('userid', None)
                my_name = session.get('my_name', None)

                return render_template('search.html', search_results=results, search_type="comments", username=my_name,
                                       userid=userid, loggedin=True)

            return render_template('search.html', search_results=results, search_type="comments", loggedin=False)

        elif search_type == "photo":

            key_words = search_word.split(" ")
            for i in range(len(key_words)):
                if key_words[i][0] != '#':
                    key_words[i] = '#'+key_words[i]

            results = photo_search(key_words)

            if session.get('loggedin', None):

                userid = session.get('userid', None)
                my_name = session.get('my_name', None)

                return render_template('search.html', search_results=results, search_type="photos", username=my_name,
                                       userid=userid, loggedin=True)

            return render_template('search.html', search_results=results, search_type="photos", loggedin=False)

        elif search_type == "user":
            names = []
            key_words = search_word.split(" ")
            if len(key_words) < 2:
                key_words.append('')

            query4 = "SELECT user_id, first_name, last_name FROM USERS"
            cursor.execute(query4)

            for item in cursor:
                names.append([int(item[0]), item[1], item[2]])

            for name in names:
                if key_words[0] == name[1] and key_words[1] == name[2]:
                    results.append(name)

            for name in names:
                if (key_words[0] == name[1] or key_words[1] == name[2]) and (name not in results):
                    results.append(name)

            for name in names:
                if (key_words[1] == name[0] or key_words[0] == name[1]) and (name not in results):
                    results.append(name)

            results = [[x[0], ' '.join([x[1], x[2]])] for x in results]

            if session.get('loggedin', None):

                userid = session.get('userid', None)
                my_name = session.get('my_name', None)

                return render_template('search.html', search_results=results, search_type="users", username=my_name,
                                       userid=userid, loggedin=True)

            return render_template('search.html', search_results=results, search_type="users", loggedin=False)

        if session.get('loggedin', None):
            userid = session.get('userid', None)
            my_name = session.get('my_name', None)

            return render_template('search.html', search_results=results, username=my_name,
                                   userid=userid, loggedin=True)

        return render_template('search.html', search_results=results, loggedin=False)

    if session.get('loggedin', None):
        userid = session.get('userid', None)
        my_name = session.get('my_name', None)

        return render_template('search.html', search_results=results, username=my_name,
                               userid=userid, loggedin=True)

    return render_template('search.html', search_results=results, loggedin=False)

def compute_jaccard_index(set_1, set_2):
    n = len(set_1.intersection(set_2))
    return n / float(len(set_1) + len(set_2) - n)


def friend_recommendation(userid, friends):

    friends = [int(x) for x in friends]

    def get_friends(id):
        query = 'SELECT user_id1, user_id2 FROM FRIENDSHIP'
        cursor.execute(query)
        friends = []
        for item in cursor:
            if int(id) == int(item[0]):
                friends.append(int(item[1]))
            elif int(id) == int(item[1]):
                friends.append(int(item[0]))

        return friends

    def get_name(id):
        query = 'SELECT user_id, first_name, last_name FROM USERS'
        cursor.execute(query)
        for item in cursor:
            if int(item[0]) == int(id):
                return item[1]+' '+item[2]

    suggestions = dict()

    for i in range(len(friends)):
        one_hop_friends = get_friends(friends[i])
        for i in range(len(one_hop_friends)):
            if one_hop_friends[i] != int(userid) and (one_hop_friends[i] not in friends):
                if one_hop_friends[i] not in suggestions.keys():
                    suggestions[one_hop_friends[i]] = 1
                else:
                    suggestions[one_hop_friends[i]] += 1

    sug_friends = suggestions.items()

    sug_friends = list(reversed(sorted(sug_friends, key=lambda x : x[1])))

    return [[x[0], get_name(x[0])] for x in sug_friends]

if __name__=='__main__':
    app.secret_key = os.urandom(100)
    app.run(debug=True)
