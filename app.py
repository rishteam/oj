#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from form import FormRegister
from models import Problem, Account, Submission
import datetime
from exts import db
from form import *
from werkzeug.security import generate_password_hash, check_password_hash
import config
from flask_login import login_user, current_user, login_required, LoginManager, logout_user

# Dealing with the path problem
import sys
sys.path.append('page')
sys.path.append('judger')

LISTEN_ALL = True

from ext_app import app

# Register blueprints
from submit import submit
app.register_blueprint(submit.submit_page)

from oj_test import test
app.register_blueprint(test.test_page)

from submissions import submissions
app.register_blueprint(submissions.submissions_page)

login = LoginManager(app)
login.login_view = 'login'

@login.user_loader
def load_user(user_id):
	return Account.query.get(int(user_id))

@app.route('/question_list', methods=['GET', 'POST'])
def question_list():
	return render_template('question_list.html')

@app.route('/question', methods=['GET', 'POST'])
def question():
	return render_template('question.html')

@app.route('/')
def index():
	# 公告

	# 最新問題，目前列出前五個最新的問題
	uid_change_name = []
	questions = Problem.query.order_by(Problem.uid.desc()).all()
	for ques_iter in questions:
		Account_search = Account.query.filter(Account.uid == ques_iter.uid).first()
		if Account_search:
			uid_change_name.append(Account_search.username)

	# Ranklist
	all_user = Account.query.all()
	ranklist = []

	for idx in range(0,len(all_user)):
		total_submit = all_user[idx].submission.order_by(Submission.problem_id).all()
		total_ac = all_user[idx].submission.filter_by(result = "AC").all()
		tried = all_user[idx].submission.order_by(Submission.problem_id).group_by(Submission.problem_id).all()
		real_ac = all_user[idx].submission.filter_by(result = "AC").order_by(Submission.problem_id).group_by(Submission.account_id).all()
		ranklist.append((all_user[idx].username , len(total_submit), len(total_ac), len(tried), len(real_ac)))

	# real_ac sort
	ranklist.sort(key=lambda tup: tup[4], reverse=True)
	# ranklist-data(python-list): (0)username, (1)total_submit, (2)total_ac, (3)tried, (4)real_ac
	# for i in ranklist:
	# 	print(i[0],i[1],i[2],i[3],i[4])

	return render_template('index.html', questions=questions,
										 name=uid_change_name,
										 ranklist=ranklist)

@app.route('/register', methods=['GET', 'POST'])
def register():
	form =FormRegister()

	print("{} | {}".format("email", form.email.data))
	if request.method == 'POST':
		if form.validate_on_submit():
			print("validate Success")
			# catch time
			date_time = datetime.datetime.now()

			# user & email collision
			username = Account.query.filter(Account.username == form.username.data).first()
			email = Account.query.filter(Account.email == form.email.data).first()


			if username or email:
				print("Username or Email collision")
				flash('Username or Email collision')
				# return 'Username or Email collision'
			elif form.password.data != form.confirm.data:
				########for test
				print(" two password is different")
				flash('two password is different')
				#######
				# return 'two password is different'
			else:
				account = Account(username=form.username.data
					, nickname=form.nickname.data
					, password=generate_password_hash(form.password.data)
					, email=form.email.data
					, permLevel=2
					, signUpTime=date_time
					, lastLoginTime=date_time
					, icon=False)
				db.session.add(account)
				db.session.commit()
				# flash('Success Thank You')
				return redirect(url_for('login'))
		else:
			flash('Email is worng')

	return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
	form = FormLogin()
	if form.validate_on_submit():
		#  當使用者按下login之後，先檢核帳號是否存在系統內。

		user = Account.query.filter_by(username=form.username.data).first()
		if user:
			#  當使用者存在資料庫內再核對密碼是否正確。
			if user.check_password(form.password.data):
				login_user(user, form.remember_me.data)
				date_time = datetime.datetime.now()
				user.lastLoginTime = date_time
				db.session.commit()
				return redirect(url_for('index'))

			else:
				#  如果密碼驗證錯誤，就顯示錯誤訊息。
				flash('Wrong Email/Username or Password')
		else:
			#  如果資料庫無此帳號，就顯示錯誤訊息。
			flash('Wrong Email/Username or Password')
	return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
	logout_user()
	# flash('Log Out See You.')
	return redirect(url_for('index'))


@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
	form = FormEdit();
	target = Account.query.filter_by(username=current_user.username).first()
	if request.method == 'POST':
		if form.validate_on_submit():
			check_coll = Account.query.filter_by(email=form.email.data).first()
			# 驗證現在密碼是否正確
			if current_user.check_password(form.current_password.data):
				flash("Current_user Password Invalid")
			# 驗證更改之密碼兩筆confirm是否相同
			if form.password.data != form.confirm.data:
				flash("Password Invalid")
			# 驗證email是否有碰撞
			if form.email.data == check_coll:
				flash("Email collision")
			else:
				target.nickname = form.nickname.data
				target.email = form.email.data
				target.password = generate_password_hash(form.password.data)
				db.session.commit()
		else:
			flash("Edit Fail")


	return render_template('edit.html', form=form)


@app.route('/userinfo/<string:name>')
def userinfo(name):
	target = Account.query.filter_by(username=name).first()

	total_submit = target.submission.order_by(Submission.problem_id).all()
	total_ac = real_ac = target.submission.filter_by(result = "AC").all()
	tried = target.submission.order_by(Submission.problem_id).group_by(Submission.problem_id).all()
	real_ac = target.submission.filter_by(result = "AC").order_by(Submission.problem_id).group_by(Submission.account_id).all()

	# print("AC:{}".format(len(real_ac)))
	# print("Try-and-no-AC:{}".format( len(tried)-len(real_ac) ))
	# print("AC-Rate:{}/{}".format(len(total_ac), len(total_submit)))

	if target:
		return render_template('userinfo.html', info=target
											  , total_submit=total_submit
											  , total_ac=total_ac
											  , tried=tried
											  , real_ac=real_ac)
	else:
		#Todo (halloworld) response 404
		return redirect(url_for('index'))

if __name__ == '__main__':
	if LISTEN_ALL:
		app.run(host='0.0.0.0')
	else:
		app.run()
