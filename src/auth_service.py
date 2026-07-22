import re, hashlib, secrets, random, string
from datetime import datetime, timedelta
from src.config import get_secret, get_int_secret, get_timer_config
from src.database import (create_user, get_user_by_username, get_user_by_email, update_user_password, update_user_profile, get_password_history, save_password_reset_code, get_valid_password_reset_code, mark_reset_code_used, save_login_otp, get_valid_login_otp, mark_login_otp_used, get_rate_limit, upsert_rate_limit, reset_rate_limit)
from src.email_sender import send_email_from_app

MIN_PASSWORD_LENGTH=10; MAX_PASSWORD_LENGTH=16; PASSWORD_HISTORY_LIMIT=3; ALLOWED_SPECIALS='@#!'; ALLOWED_PASSWORD_REGEX=re.compile(r'^[A-Za-z0-9@#!]+$')


def _now(): return datetime.now()
def _fmt(dt): return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None
def _parse(dt):
    if not dt: return None
    try: return datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    except Exception: return None

def get_password_expiry_days(): return get_int_secret('PASSWORD_EXPIRY_DAYS',60)
def get_login_otp_expiry_seconds(): return get_int_secret('LOGIN_OTP_EXPIRY_SECONDS',60)
def get_login_otp_resend_seconds(): return get_int_secret('LOGIN_OTP_RESEND_SECONDS',60)
def get_login_otp_max_resends(): return get_int_secret('LOGIN_OTP_MAX_RESENDS',5)
def get_login_otp_lockout_minutes(): return get_int_secret('LOGIN_OTP_LOCKOUT_MINUTES',60)
def get_reset_code_expiry_seconds(): return get_int_secret('RESET_CODE_EXPIRY_SECONDS',60)
def get_reset_code_resend_seconds(): return get_int_secret('RESET_CODE_RESEND_SECONDS',60)
def get_reset_code_max_resends(): return get_int_secret('RESET_CODE_MAX_RESENDS',5)
def get_reset_code_lockout_minutes(): return get_int_secret('RESET_CODE_LOCKOUT_MINUTES',60)
def get_temp_password_resend_seconds(): return get_int_secret('TEMP_PASSWORD_RESEND_SECONDS',60)
def get_temp_password_max_resends(): return get_int_secret('TEMP_PASSWORD_MAX_RESENDS',5)
def get_temp_password_lockout_minutes(): return get_int_secret('TEMP_PASSWORD_LOCKOUT_MINUTES',60)

def validate_password_policy(password):
    if not password: return False,'Password is required.'
    if len(password)<MIN_PASSWORD_LENGTH: return False,f'Password must be at least {MIN_PASSWORD_LENGTH} characters.'
    if len(password)>MAX_PASSWORD_LENGTH: return False,f'Password must not be more than {MAX_PASSWORD_LENGTH} characters.'
    if not ALLOWED_PASSWORD_REGEX.match(password): return False,'Password can contain only uppercase letters, lowercase letters, numbers 0-9, and @, #, !.'
    if not re.search(r'[A-Z]',password): return False,'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]',password): return False,'Password must contain at least one lowercase letter.'
    if not re.search(r'[0-9]',password): return False,'Password must contain at least one number.'
    if not re.search(r'[@#!]',password): return False,'Password must contain at least one special character: @, #, or !.'
    if has_repeated_character_run(password): return False,'Password must not contain same character repeated 4 or more times.'
    if has_sequential_pattern(password): return False,'Password must not contain sequential patterns like 1234, 12345, abcd, or dcba.'
    return True,'Password policy validation passed.'

def has_repeated_character_run(password, run_length=4):
    prev=''; count=1
    for ch in password.lower():
        if ch==prev:
            count+=1
            if count>=run_length: return True
        else:
            count=1; prev=ch
    return False

def has_sequential_pattern(password, sequence_length=4):
    t=password.lower(); seqs=['0123456789','9876543210','abcdefghijklmnopqrstuvwxyz','zyxwvutsrqponmlkjihgfedcba']
    return any(seq[i:i+sequence_length] in t for seq in seqs for i in range(len(seq)-sequence_length+1))

def password_policy_text():
    return f'''Password rules:\n- Length between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH}.\n- Allowed: A-Z, a-z, 0-9, @ # !.\n- At least one uppercase, lowercase, number, and @/#/!.\n- No sequential values like 1234/abcd and no same character repeated 4 times.\n- Last {PASSWORD_HISTORY_LIMIT} passwords cannot be reused.\n- Password expires after {get_password_expiry_days()} days.'''

def hash_password(password):
    salt=secrets.token_hex(16); ph=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),100000).hex(); return f'{salt}${ph}'

def verify_password(password, stored):
    try:
        salt,ph=stored.split('$'); return hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),100000).hex()==ph
    except Exception: return False

def password_was_used_recently(username,new_password): return any(verify_password(new_password,h) for h in get_password_history(username,PASSWORD_HISTORY_LIMIT))
def is_password_expired(password_changed_at):
    dt=_parse(password_changed_at)
    return True if not dt else _now() >= dt + timedelta(days=get_password_expiry_days())

def generate_initial_password(length=12):
    length=max(MIN_PASSWORD_LENGTH,min(length,MAX_PASSWORD_LENGTH))
    while True:
        chars=[secrets.choice(string.ascii_uppercase),secrets.choice(string.ascii_lowercase),secrets.choice(string.digits),secrets.choice(ALLOWED_SPECIALS)]
        chars.extend(secrets.choice(string.ascii_letters+string.digits+ALLOWED_SPECIALS) for _ in range(length-len(chars)))
        secrets.SystemRandom().shuffle(chars); pwd=''.join(chars)
        if validate_password_policy(pwd)[0]: return pwd

def _check_and_increment_rate(category, identifier, resend_seconds, max_resends, lock_minutes):
    row=get_rate_limit(category,identifier); now=_now()
    if row:
        _,_,_,count,cooldown,locked,_,_=row; count=count or 0; cd=_parse(cooldown); lu=_parse(locked)
        if lu and now < lu:
            return False, f'Maximum resend attempts reached. Please try again after {int((lu-now).total_seconds())} seconds.', count, cd, lu
        if cd and now < cd:
            return False, f'Please wait {int((cd-now).total_seconds())} seconds before resending.', count, cd, lu
        if count >= max_resends:
            lu=now+timedelta(minutes=lock_minutes); upsert_rate_limit(category,identifier,count,_fmt(cd),_fmt(lu))
            return False, f'Maximum resend attempts reached. Please try again after {lock_minutes} minutes.', count, cd, lu
        count+=1
    else:
        count=1
    cd=now+timedelta(seconds=resend_seconds); upsert_rate_limit(category,identifier,count,_fmt(cd),None)
    return True,'Allowed',count,cd,None

def get_rate_limit_status(category, identifier):
    row=get_rate_limit(category,identifier)
    if not row: return {'resend_count':0,'cooldown_remaining':0,'locked_remaining':0}
    _,_,_,count,cooldown,locked,_,_=row; now=_now(); cd=_parse(cooldown); lu=_parse(locked)
    return {'resend_count': count or 0, 'cooldown_remaining': max(0,int((cd-now).total_seconds())) if cd else 0, 'locked_remaining': max(0,int((lu-now).total_seconds())) if lu else 0}

def send_initial_password_email(username,email,temporary_password):
    subject='Initial Login Password - Invoice Reconciliation Agent'; body=f'''Hello {username},\n\nUsername: {username}\nTemporary Password: {temporary_password}\n\nYou must change this temporary password during your first login.\n\n{password_policy_text()}\n\nRegards,\nInvoice Reconciliation Agent'''
    try: send_email_from_app(email,'','',subject,body); return True,'Initial password email sent successfully.'
    except Exception as e: return False,f'Initial password email failed: {e}'

def send_password_changed_email(username,email,context='password reset'):
    try: send_email_from_app(email,'','','Password Changed - Invoice Reconciliation Agent',f'Hello {username},\n\nYour password was changed successfully.\n\nChange type: {context}\n\nRegards,\nInvoice Reconciliation Agent'); return True,'Password change notification sent.'
    except Exception as e: return False,f'Password changed, but notification email failed: {e}'

def request_login_otp(username, is_resend=False):
    user=get_user_by_username(username)
    if not user: return False,'User not found.',None
    uid,db_username,email,_,role,is_active,_,_,_=user
    allowed,msg,count,cd,lu=_check_and_increment_rate('LOGIN_OTP', db_username, get_login_otp_resend_seconds(), get_login_otp_max_resends(), get_login_otp_lockout_minutes())
    if not allowed: return False,msg,{'username':db_username,'email':email,'role':role,'resend_count':count,'cooldown_until':_fmt(cd),'locked_until':_fmt(lu)}
    otp=str(random.randint(100000,999999)); expires=_now()+timedelta(seconds=get_login_otp_expiry_seconds()); save_login_otp(db_username,email,otp,_fmt(expires))
    try: send_email_from_app(email,'','','Login OTP - Invoice Reconciliation Agent',f'Hello {db_username},\n\nYour OTP is: {otp}\n\nIt expires in {get_login_otp_expiry_seconds()} seconds.'); return True,'Login OTP sent successfully.',{'username':db_username,'email':email,'role':role,'otp_expires_at':_fmt(expires),'resend_count':count,'cooldown_until':_fmt(cd)}
    except Exception as e: return False,f'Login OTP email failed: {e}',{'username':db_username,'email':email,'role':role}

def verify_login_otp(username,otp_code):
    rec=get_valid_login_otp(username,otp_code)
    if not rec: return False,'Invalid or already used OTP.'
    oid,db_username,email,otp,used,expires,created=rec; exp=_parse(expires)
    if not exp or _now()>exp: return False,'OTP has expired. Please login again.'
    mark_login_otp_used(oid); reset_rate_limit('LOGIN_OTP', db_username); return True,'OTP verified successfully.'

def authenticate_user(username,password):
    user=get_user_by_username(username)
    if not user: return False,'Invalid username or password.',None
    uid,db_username,email,ph,role,is_active,created,must_change,changed=user
    if int(is_active)!=1: return False,'User is not active. Please contact admin.',None
    if not verify_password(password,ph): return False,'Invalid username or password.',None
    return True,'Password verified successfully. OTP is required to continue.',{'id':uid,'username':db_username,'email':email,'role':role,'is_active':is_active,'must_change_password':must_change,'password_expired':is_password_expired(changed)}

def create_default_admin():
    username=get_secret('DEFAULT_ADMIN_USERNAME','admin'); email=get_secret('DEFAULT_ADMIN_EMAIL',get_secret('SMTP_EMAIL','admin@example.com')).strip().lower()
    if get_user_by_username(username): return
    pwd=generate_initial_password(12); create_user(username,email,hash_password(pwd),'Admin',1,1); send_initial_password_email(username,email,pwd)

def has_permission(role,permission):
    return permission in {'Admin':['view','edit','send_email','manage_users'],'Editor':['view','edit'],'Email Sender':['view','send_email'],'Viewer':['view'],'Pending':[]}.get(role,[])

def request_password_reset(username_or_email, is_resend=False):
    user=get_user_by_username(username_or_email.strip()) or get_user_by_email(username_or_email.strip().lower())
    if not user: return False,'No user found with this username or email.',None
    uid,username,email,_,role,is_active,_,_,_=user
    if int(is_active)!=1: return False,'User account is inactive. Please contact admin.',None
    allowed,msg,count,cd,lu=_check_and_increment_rate('RESET_CODE', username, get_reset_code_resend_seconds(), get_reset_code_max_resends(), get_reset_code_lockout_minutes())
    if not allowed: return False,msg,{'username':username,'email':email,'resend_count':count,'cooldown_until':_fmt(cd),'locked_until':_fmt(lu)}
    code=str(random.randint(100000,999999)); exp=_now()+timedelta(seconds=get_reset_code_expiry_seconds()); save_password_reset_code(username,email,code,_fmt(exp))
    try: send_email_from_app(email,'','','Password Reset Code - Invoice Reconciliation Agent',f'Hello {username},\n\nYour reset code is: {code}\n\nIt expires in {get_reset_code_expiry_seconds()} seconds.\n\n{password_policy_text()}'); return True,'Password reset code sent successfully.',{'username':username,'email':email,'reset_expires_at':_fmt(exp),'resend_count':count,'cooldown_until':_fmt(cd)}
    except Exception as e: return False,f'Reset code generated but email sending failed: {e}',{'username':username,'email':email}

def reset_password_with_code(username, reset_code, new_password):
    ok,msg=validate_password_policy(new_password)
    if not ok: return False,msg
    if password_was_used_recently(username,new_password): return False,f'You cannot reuse your last {PASSWORD_HISTORY_LIMIT} passwords.'
    rec=get_valid_password_reset_code(username,reset_code)
    if not rec: return False,'Invalid or already used reset code.'
    rid,db_username,email,code,used,expires,created=rec; exp=_parse(expires)
    if not exp or _now()>exp: return False,'Reset code has expired. Please request a new code.'
    update_user_password(db_username,hash_password(new_password),0); mark_reset_code_used(rid); reset_rate_limit('RESET_CODE', db_username); send_password_changed_email(db_username,email,'forgot password reset'); return True,'Password reset successful. Please login with your new password.'

def change_password_first_login(username,new_password):
    ok,msg=validate_password_policy(new_password)
    if not ok: return False,msg
    if password_was_used_recently(username,new_password): return False,f'You cannot reuse your last {PASSWORD_HISTORY_LIMIT} passwords.'
    user=get_user_by_username(username)
    if not user: return False,'User not found.'
    _,db_username,email,_,_,_,_,_,_=user; update_user_password(db_username,hash_password(new_password),0); send_password_changed_email(db_username,email,'first-time or expired password change'); return True,'Password changed successfully. Please login again.'

def send_temporary_password_for_user(username):
    user=get_user_by_username(username)
    if not user: return False,'User not found.',None,False,None
    uid,db_username,email,_,role,is_active,_,_,_=user
    if int(is_active)!=1: return False,'User account is inactive. Activate the user before sending a temporary password.',email,False,None
    allowed,msg,count,cd,lu=_check_and_increment_rate('TEMP_PASSWORD', db_username, get_temp_password_resend_seconds(), get_temp_password_max_resends(), get_temp_password_lockout_minutes())
    if not allowed: return False,msg,email,False,None
    pwd=generate_initial_password(12); update_user_password(db_username,hash_password(pwd),1); success,email_msg=send_initial_password_email(db_username,email,pwd)
    if success: return True,'Temporary password sent successfully. User must reset password on next login.',email,True,None
    return True,f'Temporary password generated and set, but email failed: {email_msg}',email,False,pwd

