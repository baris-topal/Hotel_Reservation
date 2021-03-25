#gerekli kütüphaneleri çekiyoruz
import datetime
import hashlib
from datetime import date
from flask import Flask, request, render_template_string, render_template, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, join, and_, MetaData
from flask_user import current_user, login_required, roles_required, UserManager, UserMixin, user_logged_in, user_logged_out
from sqlalchemy.sql import table, column, select 
from functools import wraps

#kullanılacak global değişkenleri tanımlıyoruz
sorgu_kullanici_id = None
sorgu_kazanilan_puan = 0
sorgu_kullanici_puan = 0


#login erişim düzeyi için fonksiyon tanımlıyoruz
#koşulun sağlanmaması durumunda uyarı verip login
#fonksiyonuna yönlendiriyoruz
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash("Öncelikle giriş yapmalısınız!")
            return redirect(url_for('login'))
    return wrap

#admin erişim düzeyi için fonksiyon tanımlıyoruz
#koşulun sağlanmaması durumunda uyarı veriyor ve
#anasayfa fonksiyonuna yönlendiriyoruz
def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session.get('admin'):
            return f(*args, **kwargs)
        else:
            flash("Bu sayfa için yetkiniz bulunmamaktadır.")
            return redirect(url_for('home_page'))
    return wrap


#veritabanının yolunu gösteriyoruz
db_uri = 'sqlite:///otel_rezervasyon.sqlite'
engine = create_engine(db_uri)


#uygulamamaız için ön ayarları yapılandırıyor ve
#mail onayı için gerekli ayarları giriyoruz
class ConfigClass(object):
    """ Flask application config """
    SECRET_KEY = 'This is an INSECURE secret!!   NOT use this in production!!'
    
    SQLALCHEMY_DATABASE_URI = 'sqlite:///otel_rezervasyon.sqlite'
    SQLALCHEMY_TRACK_MODIFICATIONS = False    # Avoids SQLAlchemy warning
 
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USE_TLS = False
    MAIL_USERNAME = 'otel.motel.765@gmail.com' # gmail adresinizi girin
    MAIL_PASSWORD = 'Python_35' # gmail şifrenizi girin
    MAIL_DEFAULT_SENDER = '"Test" <otel.motel.765@gmail.com>'

    # Flask-User settings
    USER_APP_NAME = "Tribago"      # Shown in and email templates and page footers
    USER_ENABLE_EMAIL = True        # Enable email authentication
    USER_ENABLE_USERNAME = False    # Disable username authentication
    USER_EMAIL_SENDER_NAME = USER_APP_NAME
    USER_EMAIL_SENDER_EMAIL = "noreply@example.com"
   # Daha detaylı bilgi https://flask-user.readthedocs.io/en/latest/configuring_settings.html de bulunabilir.


#uygulamamızın main fonksiyonunu oluşturuyoruz
def create_app():
    """ Flask application factory """
    
    #ayar yapılandırmamızı içe aktarıyoruz
    app = Flask(__name__)
    app.config.from_object(__name__+'.ConfigClass')

    db = SQLAlchemy(app)

    #tablolarımızı oluşturuyoruz
    class User(db.Model, UserMixin):
        
        __tablename__ = 'users'
        kullanici_id = db.Column(db.Integer, primary_key=True)

        email = db.Column(db.String(50), nullable=False, unique=True)
        email_confirmed_at = db.Column(db.DateTime())
        password = db.Column(db.String(50), nullable=False)

        kullanici_adi = db.Column(db.String(50))
        kullanici_soyadi = db.Column(db.String(50))
        kullanici_tcno = db.Column(db.Integer())
        kullanici_telno = db.Column(db.Integer())
        kullanici_puan = db.Column(db.Float(), server_default='0')
        kullanici_rol = db.Column('adminlik', db.Boolean())

        def __init__(self, email, password, kullanici_adi, kullanici_soyadi, kullanici_tcno, kullanici_telno, email_confirmed_at, kullanici_rol):
            self.email = email
            self.password = password
            self.kullanici_adi = kullanici_adi
            self.kullanici_soyadi = kullanici_soyadi
            self.kullanici_tcno = kullanici_tcno
            self.kullanici_telno = kullanici_telno
            self.email_confirmed_at = email_confirmed_at
            self.kullanici_rol = kullanici_rol

    class Otel(db.Model):
        __tablename__ = 'oteller'
        otel_id = db.Column(db.Integer(),primary_key = True)
        otel_adi = db.Column(db.String(100),nullable = False)
        otel_sehir = db.Column(db.Integer(), nullable=False)
        otel_yildizi= db.Column(db.Integer(), nullable=False)

        def __init__(self, otel_adi, otel_sehir, otel_yildizi):
            self.otel_adi = otel_adi
            self.otel_sehir = otel_sehir
            self.otel_yildizi = otel_yildizi

    class Oda(db.Model):
        __tablename__ = 'odalar'
        oda_id = db.Column(db.Integer(),primary_key = True)
        otel_id = db.Column(db.Integer,db.ForeignKey('oteller.otel_id',ondelete='CASCADE'))
        oda_adi = db.Column(db.String(50),nullable = False)
        oda_tipi = db.Column(db.String(50),nullable = False)
        oda_fiyat = db.Column(db.Float())
        oda_durum = db.Column(db.Boolean(), server_default='0')

        def __init__(self, otel_id, oda_adi, oda_tipi, oda_fiyat):
            self.otel_id = otel_id
            self.oda_adi = oda_adi
            self.oda_tipi = oda_tipi
            self.oda_fiyat = oda_fiyat
        

    class Sepet(db.Model):
        __tablename__ = 'sepetler'
        sepet_id = db.Column(db.Integer(),primary_key = True)
        user_id = db.Column(db.Integer(), db.ForeignKey('users.kullanici_id', ondelete='CASCADE'))
        oda_id = db.Column(db.Integer(),db.ForeignKey('odalar.oda_id', ondelete='CASCADE'))
        otel_id = db.Column(db.Integer,db.ForeignKey('oteller.otel_id',ondelete='CASCADE'))
        toplam_tutar = db.Column(db.Float())
        rezerve_tarih = db.Column(db.DateTime(), nullable = False)
        giris_tarih = db.Column(db.Date())
        cikis_tarih = db.Column(db.Date())
        kalinacak_gun = db.Column(db.Integer())
        sepet_durum = db.Column(db.Boolean(), server_default='0')

        def __init__(self, user_id, otel_id, oda_id, toplam_tutar,rezerve_tarih, giris_tarih, cikis_tarih, kalinacak_gun):
            self.user_id = user_id
            self.otel_id = otel_id
            self.oda_id = oda_id
            self.toplam_tutar = toplam_tutar
            self.rezerve_tarih = rezerve_tarih
            self.giris_tarih = giris_tarih
            self.cikis_tarih = cikis_tarih
            self.kalinacak_gun = kalinacak_gun
  
    user_manager = UserManager(app, db, User)
    
    #veritabanımızı oluşturuyor ve tablolara erişim
    #için takma isimler veriyoruz
    db.create_all()
    engine = create_engine('sqlite:///otel_rezervasyon.sqlite')
    meta = MetaData(engine,reflect=True)
    table_users = meta.tables['users']
    table_otel = meta.tables['oteller']
    table_oda = meta.tables['odalar']
    table_sepet = meta.tables['sepetler']
   

    #sistemde admin kayıtlı değilse bir admin oluşturuyoruz
    if not User.query.filter(User.email == 'admin@example.com').first():
        #şifremizi hashli bir şekilde tutmak için fonksiyona tabi tutuyoruz
        tmp_psw= '12345678'
        tmp_psw = hashlib.md5(tmp_psw.encode())
        tmp_psw = tmp_psw.hexdigest()
            
        user = User(
            email='admin@example.com',
            
            password=tmp_psw,
            email_confirmed_at=datetime.datetime.utcnow(),
            kullanici_adi = None,
            kullanici_soyadi = None,
            kullanici_tcno = None,
            kullanici_telno = None,
            kullanici_rol = 1
        )
        db.session.add(user)
        db.session.commit()

    #anasayfaya yönlendirme fonksiyonumuzu oluşturuyoruz
    @app.route('/')
    def home_page():
        return render_template("index.html")

    #giriş yap fonksiyonumuzu oluşturuyoruz,
    #formdan gelen verileri veritabanındaki
    #veriler ile karşılaştırıyoruz, uyuşması
    #durumunda sisteme giriş yapılıyor.
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form['email']
            #şifremizi veritabanında ki hashli hali ile karşılaştırıyoruz
            tmp_psw=request.form['password']
            tmp_psw = hashlib.md5(tmp_psw.encode())
            tmp_psw = tmp_psw.hexdigest()
            password = tmp_psw

            try:
                #böyle bir email ve şifre uyuşması var mı sorgusu yapıyoruz
                sorgu1 = User.query.filter_by(email = email, password = password).first()
                if sorgu1 is not None:
                    
                    #diğer fonksiyonlarda kullanmak üzere girilen emailin kullanıcı id sini alıyoruz
                    global sorgu_kullanici_id
                    conn=engine.connect()
                    select_st=select([table_users.c.kullanici_id]).where(table_users.c.email == email)
                    sorgu_kullanici_id=conn.execute(select_st).scalar()             

                    #bu kullanıcı admin mi sorgusu yapıyoruz
                    sorgu2 = User.query.filter_by(email = email, password = password, kullanici_rol = 1).first()
                    if sorgu2 is not None:
                        session['admin']=True

                    session['logged_in']=True
                    flash('Hoşgeldiniz')

                    return redirect(url_for('home_page'))
                else:
                    flash('Kullanıcı adı veya şifre yanlış')
                    return redirect(url_for('home_page'))
            except: 
                flash('Beklenmeyen bir hata oluştu!')
                return redirect(url_for('home_page'))
        
        else:
            return redirect(url_for('home_page'))


    #login fonksiyonun aynısı fakat yönlendirdiği kısım farklı
    @app.route('/rezerve_login', methods=['GET', 'POST'])
    def rezerve_login():
        if request.method == 'POST':
            email= request.form['email']
            tmp_psw=request.form['password']
            tmp_psw = hashlib.md5(tmp_psw.encode())
            tmp_psw = tmp_psw.hexdigest()
            password = tmp_psw

            try:
                sorgu1 = User.query.filter_by(email = email, password = password).first()
                if sorgu1 is not None:
                    global sorgu_kullanici_id
                    conn=engine.connect()
                    select_st=select([table_users.c.kullanici_id]).where(table_users.c.email == email)
                    sorgu_kullanici_id =conn.execute(select_st).scalar()  

                    sorgu2 = User.query.filter_by(email = email, password = password, kullanici_rol = 1).first()
                    if sorgu2 is not None:
                        session['admin']=True

                    session['logged_in']=True
                    flash('Hoşgeldiniz')

                    #tekrar rezerve fonksiyonuna gitmesini sağlıyoruz
                    return redirect(url_for('rezerve'))
                else:
                    flash('Kullanıcı adı veya şifre yanlış')
                    return redirect(url_for('rezerve'))
            except: 
                flash('Beklenmeyen bir hata oluştu!')
                return redirect(url_for('rezerve'))
        
        else:
            return redirect(url_for('rezerve'))

    #kullan
    @app.route("/logout")
    @login_required
    def logout():
        conn = engine.connect()
        select_st=table_sepet.delete().where(and_(table_sepet.c.user_id==sorgu_kullanici_id, table_sepet.c.sepet_durum ==0 ))
        conn.execute(select_st)
        session.clear()
        flash("Başarı ile çıkış yaptınız.")

        return redirect(url_for('home_page'))


    @app.route('/', methods=['GET','POST'])
    def uye_ol():
        if request.method == 'POST':
            tmp_psw=request.form['parola']
            tmp_psw = hashlib.md5(tmp_psw.encode())
            tmp_psw = tmp_psw.hexdigest()
            password = tmp_psw
            try:
                new_user = User(
                    kullanici_tcno= request.form['tcno'],
                    kullanici_adi= request.form['adi'],
                    kullanici_soyadi = request.form['soyadi'],
                    kullanici_telno= request.form['telno'],
                    email= request.form['email'],
                    password=password,
                    kullanici_rol = 0,
                    email_confirmed_at=datetime.datetime.utcnow())

                db.session.add(new_user)
                db.session.commit()
                flash("Kayıt başarı ile eklendi")
            except:
                flash("Kayıt işlemi sırasında hata oluştu")

            finally:
                return redirect(url_for('home_page'))


    @app.route('/uye_gor', methods=['GET','POST'])
    @login_required
    @admin_required
    def uye_gor():
        conn = engine.connect()
        select_st=select([table_users.c.kullanici_id, table_users.c.kullanici_adi, table_users.c.kullanici_soyadi, 
        table_users.c.kullanici_tcno, table_users.c.email, table_users.c.kullanici_telno]).where(table_users.c.adminlik==0)
        rows = conn.execute(select_st)

        return render_template("uye_gor.html", rows =rows)


    @app.route('/uye_sil/<id>')
    @login_required
    @admin_required
    def uye_sil(id=0):
        conn = engine.connect()
        select_st=table_users.delete().where(table_users.c.kullanici_id==id)
        rows=conn.execute(select_st)

        return redirect(url_for('uye_gor'))


    @app.route('/otel_listele', methods=['GET','POST'])
    @login_required
    @admin_required
    def otel_listele():
        if request.method == 'POST':
            new_otel = Otel(
                otel_adi= request.form['oteladi'],
                otel_sehir= request.form['otelsehir'],
                otel_yildizi = request.form['otelyildizi'])

            db.session.add(new_otel)
            db.session.commit()
            return redirect(url_for('otel_listele'))

        
        conn = engine.connect()
        select_st=select([table_otel.c.otel_id, table_otel.c.otel_adi, table_otel.c.otel_sehir, table_otel.c.otel_yildizi])
        rows = conn.execute(select_st)
        return render_template("otel_listele.html", rows =rows)


    @app.route('/otel_duzenle/<id>',methods=['GET','POST'])
    @login_required
    @admin_required
    def otel_duzenle(id=0):
        if request.method=='POST':
            otel_adi = request.form['oteladi']
            otel_sehir = request.form['otelsehir']
            otel_yildizi = request.form['otelyildizi']
            conn=engine.connect()
            select_st1=table_otel.update().where(table_otel.c.otel_id==id).values(otel_adi = otel_adi, otel_sehir = otel_sehir, otel_yildizi = otel_yildizi)
            conn.execute(select_st1)
            return redirect(url_for('otel_listele'))
        else:
            conn=engine.connect()
            select_st2=select([table_otel.c.otel_adi, table_otel.c.otel_sehir, table_otel.c.otel_yildizi]).where(table_otel.c.otel_id== id)
            rows=conn.execute(select_st2)
            return render_template("otel_duzenle.html", tmp_otel_id = id, rows = rows)


    @app.route('/otel_sil/<id>')
    @login_required
    @admin_required
    def otel_sil(id=0):
        conn = engine.connect()
        select_st=table_otel.delete().where(table_otel.c.otel_id==id)
        rows=conn.execute(select_st)
        
        return redirect(url_for('otel_listele'))

    
    @app.route('/oda_listele', methods=['GET','POST'])
    @login_required
    @admin_required
    def oda_listele():
        if request.method=='POST':
            if request.form['btn']=='Ekle':
                try:
                    new_oda = Oda(
                        otel_id = request.form['id'],
                        oda_adi = request.form['odaadi'],
                        oda_tipi = request.form['odatipi'],
                        oda_fiyat = request.form['odafiyat'])

                    db.session.add(new_oda)
                    db.session.commit()
                    flash("Kayıt başarı ile eklendi")
                    return redirect(url_for('oda_listele'))
                except:
                    flash("Kayıt işlemi sırasında hata oluştu")
            elif request.form['btn']=='Seç':
                otel_id = request.form['otel_id']
                conn = engine.connect()
                select_st=select([table_otel.c.otel_id,table_otel.c.otel_adi])
                rows_otel = conn.execute(select_st)

                select_st1=select([table_oda.c.oda_id,table_oda.c.oda_adi,table_oda.c.otel_id, table_oda.c.oda_tipi, table_oda.c.oda_fiyat]).where(table_oda.c.otel_id==otel_id)
                rows_oda = conn.execute(select_st1)
                return render_template("oda_listele.html", rows =rows_oda,rows2=rows_otel,otel_id=otel_id)

        conn = engine.connect()
        select_st=select([table_otel.c.otel_id,table_otel.c.otel_adi])
        rows_otel = conn.execute(select_st)
        
        return render_template("oda_listele.html",rows2=rows_otel)

                    
    @app.route('/oda_duzenle/<id>',methods=['GET','POST'])
    @login_required
    @admin_required
    def oda_duzenle(id=0):
        if request.method=='POST':
            oda_adi = request.form['odaadi']
            oda_tipi = request.form['odatipi']
            oda_fiyat = request.form['odafiyat']
            conn=engine.connect()
            select_st1=table_oda.update().where(table_oda.c.oda_id==id).values(oda_adi = oda_adi, oda_tipi = oda_tipi, oda_fiyat = oda_fiyat)
            conn.execute(select_st1)
            return redirect(url_for('oda_listele'))
        else:
            conn=engine.connect()
            select_st2=select([table_oda.c.oda_id, table_oda.c.oda_adi, table_oda.c.oda_tipi, table_oda.c.oda_fiyat]).where(table_oda.c.oda_id== id)
            rows=conn.execute(select_st2)
            
            return render_template("oda_duzenle.html", tmp_oda_id = id, rows = rows)


    @app.route('/oda_sil/<id>')
    @login_required
    @admin_required
    def oda_sil(id=0):
        conn = engine.connect()
        select_st=table_oda.delete().where(table_oda.c.oda_id==id)
        rows=conn.execute(select_st)

        return redirect(url_for('oda_listele'))

    
    @app.route('/rezerve',methods=['GET','POST'])  
    def rezerve():
        conn=engine.connect()
        j = table_oda.join(table_otel, table_oda.c.otel_id == table_otel.c.otel_id)
        
        stmt = select([table_oda.c.oda_id,table_oda.c.oda_adi,table_oda.c.oda_tipi,
        table_oda.c.oda_fiyat,table_otel.c.otel_sehir,table_otel.c.otel_adi,table_oda.c.otel_id]).select_from(j).where(table_oda.c.oda_durum == 0)
        rows=conn.execute(stmt)

        return render_template("rezerve.html",rows=rows)


    @app.route('/sepet_ekle/<id>', methods=['GET','POST'])
    @login_required
    def sepet_ekle(id=0):
        conn=engine.connect()

        select_st1=select([table_oda.c.oda_fiyat]).where(table_oda.c.oda_id == id)
        toplam_tutar = conn.execute(select_st1).scalar()
        print('toplam tutar: ',toplam_tutar)

        select_st2=select([table_oda.c.otel_id]).where(table_oda.c.oda_id == id)
        otel_id = conn.execute(select_st2).scalar()

        sepet = Sepet(
            user_id = sorgu_kullanici_id,
            otel_id = otel_id,
            oda_id = id,
            toplam_tutar= toplam_tutar,
            rezerve_tarih = datetime.datetime.utcnow(),
            giris_tarih = None,
            cikis_tarih= None,
            kalinacak_gun= 0
            )
        db.session.add(sepet)
        db.session.commit()

        return redirect(url_for('sepet'))


    @app.route('/sepet', methods=['GET','POST'])
    @login_required
    def sepet():
        global sorgu_kullanici_puan
        conn=engine.connect()
        j = table_oda.join(table_otel, table_oda.c.otel_id == table_otel.c.otel_id).join(table_sepet,table_oda.c.oda_id==table_sepet.c.oda_id)
        
        sorgu1 = select([table_sepet.c.sepet_id, table_oda.c.oda_id,table_oda.c.oda_adi,table_oda.c.oda_tipi,
        table_oda.c.oda_fiyat,table_otel.c.otel_sehir,table_otel.c.otel_adi,table_oda.c.otel_id]).select_from(j).where(table_sepet.c.sepet_durum == 0)
        rows=conn.execute(sorgu1)
        
        sorgu2 = select([table_users.c.kullanici_puan]).where(table_users.c.kullanici_id == sorgu_kullanici_id)
        sorgu_kullanici_puan = conn.execute(sorgu2).scalar()
        sorgu_kullanici_puan = round(sorgu_kullanici_puan, 4)

        return render_template("sepet.html",rows=rows, puan = sorgu_kullanici_puan)


    @app.route('/sepet_sepet_tarih_sec/<id>/<odaid>',methods=['GET','POST'])
    @login_required
    def sepet_tarih_sec(id=None, odaid=None):

        return render_template("sepet_onay.html", sepet_id = id, oda_id = odaid)

    
    @app.route('/sepet_duzenle/<id>/<odaid>',methods=['GET','POST'])
    @login_required
    def sepet_duzenle(id=None, odaid=None):
        if request.method=='POST':
            tmp_giris = request.form['giristarihi']
            tmp_cikis = request.form['cikistarihi']

            giris_liste = tmp_giris.split('-')
            cikis_liste = tmp_cikis.split('-')

            giris_tarih = date(int(giris_liste[0]), int(giris_liste[1]), int(giris_liste[2]))
            cikis_tarih = date(int(cikis_liste[0]), int(cikis_liste[1]), int(cikis_liste[2]))
            kalinacak_gun = request.form['kalinacakgun']
            puan_kullanma_durumu = request.form['puan']
            
            if puan_kullanma_durumu == '1':
                conn=engine.connect()
                select_st2=select([table_users.c.kullanici_puan]).where(table_users.c.kullanici_id == sorgu_kullanici_id)
                puan_kullanma_durumu = conn.execute(select_st2).scalar()
                print('puan_kullanma_durumu: ', puan_kullanma_durumu)
                 
            else:
                puan_kullanma_durumu = 0
                print('puan_kullanma_durumu: ', puan_kullanma_durumu)
            
            global sorgu_kazanilan_puan
            conn=engine.connect()
            select_st2=select([table_oda.c.oda_fiyat]).where(table_oda.c.oda_id == odaid)
            birim_fiyat = conn.execute(select_st2).scalar()
            print('birim fiyat: ', birim_fiyat)
            toplam_tutar = float(kalinacak_gun) * birim_fiyat - float(puan_kullanma_durumu)
            sorgu_kazanilan_puan = toplam_tutar * 0.03 - puan_kullanma_durumu
            print('kazanilan puan: ', sorgu_kazanilan_puan)
            
            select_st1=table_sepet.update().where(table_sepet.c.sepet_id==id).values(giris_tarih = giris_tarih, cikis_tarih = cikis_tarih, kalinacak_gun = kalinacak_gun, 
            toplam_tutar = toplam_tutar)
            conn.execute(select_st1)

        return redirect(url_for('sepet'))


    @app.route('/sepet_onay/<id>', methods=['GET','POST'])
    @login_required
    def sepet_onay(id=0):
        global sorgu_kullanici_puan
        try:
            conn = engine.connect()
            tmp_tarihzaman = datetime.datetime.utcnow()
            select_st1=table_sepet.update().where(table_sepet.c.sepet_id==id).values(sepet_durum = 1, rezerve_tarih = tmp_tarihzaman)
        
            sorgu_kullanici_puan += sorgu_kazanilan_puan
            select_st2=table_users.update().where(table_users.c.kullanici_id==sorgu_kullanici_id).values(kullanici_puan = sorgu_kullanici_puan)
        
            conn.execute(select_st1)
            conn.execute(select_st2)  
        except:
            flash('Önce tarih seçmelisiniz')
            
        return redirect(url_for('sepet'))


    @app.route('/sepet_sil/<id>', methods=['GET','POST'])
    @login_required
    def sepet_sil(id=0):
        conn = engine.connect()
        select_st1=table_sepet.delete().where(table_sepet.c.sepet_id==id)
        conn.execute(select_st1)

        return redirect(url_for('sepet'))


    @app.route('/islemlerim', methods=['GET','POST'])
    @login_required
    def islemler():
        conn=engine.connect()
        j = table_sepet.join(table_oda, table_sepet.c.oda_id == table_oda.c.oda_id).join(table_otel,table_sepet.c.otel_id==table_otel.c.otel_id)
        
        stmt = select([table_otel.c.otel_adi,table_otel.c.otel_sehir,table_otel.c.otel_id,table_oda.c.oda_adi,
        table_oda.c.oda_tipi,table_sepet.c.giris_tarih,table_sepet.c.cikis_tarih,table_sepet.c.kalinacak_gun, 
        table_sepet.c.toplam_tutar,table_sepet.c.rezerve_tarih]).select_from(j).where(and_(
        table_sepet.c.user_id == sorgu_kullanici_id, table_sepet.c.sepet_durum == 1))
        
        rows=conn.execute(stmt)
        return render_template("islem.html",rows=rows)
    

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=True)
