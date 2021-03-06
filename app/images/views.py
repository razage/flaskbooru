from datetime import datetime
from math import ceil
from operator import itemgetter
from os import remove
from os.path import join

from flask import abort, Blueprint, flash, render_template, redirect, request, url_for
from flask_login import current_user, login_required
from PIL import Image
from sqlalchemy import desc
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.utils import secure_filename

from .forms import ImageUploadForm
from .models import Images
from .utils import allowed_file, applytags, getimagehash, makethumbnail, moveimage, parsetags
from app import app, db
from app.decorators import do_nothing

mod = Blueprint('images', __name__, url_prefix="/images")


@mod.route("/")
def imagehomeredirect():
    return redirect(url_for("images.imageindex", page=1))


imageindex_loginreq = login_required if app.config['LOGINREQUIRED']['imagelist'] else do_nothing
@mod.route("/<int:page>")
@imageindex_loginreq
def imageindex(page):
    tags = []
    totalpages = ceil(db.session.query(Images).count() / app.config["IMAGESPERPAGE"])
    print(totalpages)
    images = db.session.query(Images).order_by(desc(Images.uploadtime)).offset(app.config["IMAGESPERPAGE"] * (page - 1)).limit(app.config["IMAGESPERPAGE"])
    for i in images:
        for t in i.tags:
            tags.append((t.tagnamespace, t.tagname))
    return render_template("images/imageindex.html", title="%s - Page %s" % (app.config["SITENAME"], page),
                           images=images, tags=sorted(set(tags), key=itemgetter(0, 1)), totalpages=totalpages,
                           curpage=page)


upload_loginreq = login_required if app.config['LOGINREQUIRED']['upload'] else do_nothing
@mod.route("/upload", methods=["GET", "POST"])
@upload_loginreq
def upload():
    form = ImageUploadForm()
    if form.validate_on_submit():
        img = request.files['image']
        if img and allowed_file(img.filename.lower()):
            tmpfilename = secure_filename(img.filename)
            img.save(join(app.config["IMAGETEMP"], tmpfilename))
            finalname = "%s.%s" % (getimagehash(open(join(app.config["IMAGETEMP"], tmpfilename), 'rb').read()), tmpfilename.split(".")[1])
            try:
                check = db.session.query(Images).filter(Images.imgname == finalname).one()
            except NoResultFound:
                db.session.add(Images(finalname, form.contentlevel.data, datetime.now(), current_user.username))
                db.session.commit()
                moveimage(tmpfilename, finalname)
                imagefortagging = db.session.query(Images).filter(Images.imgname == finalname).one()
                applytags(imagefortagging, parsetags(form.tagfield.data))
                makethumbnail(finalname)
                return redirect(url_for("images.upload"))
            remove(join(app.config["IMAGETEMP"], tmpfilename))
            flash("This image is already on the booru.")
            return redirect(url_for("images.upload"))
        else:
            flash("Forbidden extension!")
    for field, errors in form.errors.items():
        for error in errors:
            flash("Error in field %s - %s" % (getattr(form, field).label.text, error))
    return render_template("images/upload.html", title="Upload Image", form=form)


viewimage_loginreq = login_required if app.config['LOGINREQUIRED']['imageview'] else do_nothing
@mod.route("/view/<imgname>")
@viewimage_loginreq
def viewimage(imgname):
    try:
        test = db.session.query(Images).filter(Images.imgname == imgname).one()
        img = Image.open(join(app.config["IMAGEFOLDER"], test.imgname))
        return render_template("images/viewimage.html", image=test, resize=img.size > app.config["MAXIMAGESIZE"])
    except NoResultFound:
        abort(404)