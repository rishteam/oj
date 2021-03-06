import os
from flask import Flask, Blueprint, render_template, request, url_for, redirect
import logging, random, string
from flask_login import login_user, current_user, LoginManager
from operator import getitem
import datetime as dt
from models import Contest, Account, Problem, Submission
import utils, json
from exts import db
from judger import judge, manage

log = logging.getLogger('Contest')

contest_page = Blueprint('contest_page',
    __name__,
    template_folder=os.path.join(utils.cur_path(__file__), 'templates'),
    static_folder=os.path.join(utils.cur_path(__file__), 'static'),
    static_url_path='/contest/static')
# TODO: ?????

def gen_random_str(size=4):
	return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(size))


@contest_page.route('/contest/list', methods=['GET'])
def contest_list_view():
    status = ['??', 'Scheduled', 'Running', 'Ended']
    info = []

    # contest_info, b = .first()
    
    
    for row, username in db.session.query(Contest, Account.username).join(Account, Contest.owner == Account.uid, isouter=True):
        info.append({
            'cid': row.contest_id,
            'title': row.contest_title,
            'status': status[row.status],
            'start_time': str(row.start_time),
            'end_time': str(row.end_time),
            'remaining_time': str(row.end_time-row.start_time),
            'owner': username
        })
    
    return render_template('contest_list.html', info=info)
    
@contest_page.route('/contest/<int:cid>', methods=['GET', 'POST'])
def contest_page_view(cid):
    print(request.method)
    if request.method == 'POST':
        print('in')
        pid = int(request.form['probID'])
        lang = request.form['lang']
        code = request.form['code']

        prob = Problem.query.get(pid)
        if prob:
            info = json.loads(prob.info)
            num_td = int(info['td_num'])

            date_time = dt.datetime.now()
            sub = Submission(result='Wait'
                    , resTime=-1.0, resMem=-1.0
                    , code=code, lang=lang, rank=-1, time=date_time
                    , account=current_user, problem=prob, for_test=cid)
            db.session.add(sub)
            db.session.commit()

            log.debug('Add problem pid={} subid={}'.format(prob.problem_id, sub.submit_id))

            manage.add_judger(sub.submit_id, prob.problem_id, judge.JUDGE_CPP, code, 3.0, 65536, num_td)

    contest_info = db.session.query(Contest).filter(Contest.contest_id == cid).first()
    
    print(contest_info.problem_id)

    problem_id = []

    for i in (contest_info.problem_id.strip('\n').split(',')):
        if(i != ''):
            problem_id.append(int(i))

        # Submission
    sub_list = Submission.query
    sub_list = sub_list\
                    .order_by(Submission.submit_id.desc())\
                    .filter(Submission.for_test == cid)\
                    .all()
    for i in sub_list:
        # Rejudge button (check if the user is admin)
        if current_user.is_authenticated and current_user.permLevel <= 0:
            setattr(i, 'rejudge_link', url_for('api_blueprint.rejudge_submission', subid=i.submit_id)) # rejudge link

        # Set `submitter`
        u = Account.query.get(i.account_id)
        setattr(i, 'submitter', u.nickname if u else 'Unknown')
        setattr(i, 'username', u.username if u else None)

        # Set `codeLen`
        codeLength = '{:.2f} KiB'.format(len(i.code)/1000)
        setattr(i, 'codeLen', codeLength)

        # Set `score`
        # TODO(roy4801): implement score
        setattr(i, 'score', 'NaN')

        # CE modal
        if i.result == 'CE':
            setattr(i, 'ce_id_str', gen_random_str(8))


    print(sub_list)
    
    return render_template('contest.html', sub_list=sub_list, is_admin=current_user.is_authenticated, info={
        'cid': contest_info.contest_id,
        'title': contest_info.contest_title,
        'problem_id': problem_id,
        'start_time': contest_info.start_time,
        'end_time': contest_info.end_time
    })

# TODO Finish Create Page -- Erichsu
# watch out premlevel
@contest_page.route('/contest/create', methods=['GET', 'POST'])
def create_contest_view():

    if request.method == 'POST':
        title = request.form['Title']
        StartDate = request.form['StartDate']
        EndDate = request.form['EndDate']
        problem_num = int(request.form['problem_num'])
        problems = ''

        for i in range(problem_num):
            tmp = (request.form['problem_'+str(i+1)].split(' '))[0][1:]
            problems += tmp+','

        query = Contest(contest_title=title,
                    problem_id=problems,
                    owner=current_user.uid,
                    start_time = StartDate,
                    end_time = EndDate,
                    status = 1)
        db.session.add(query)
        db.session.commit()

        log.debug('Add Contest title={}'.format(title))

    return render_template('create_contest.html')


@contest_page.route('/contest/getproblem', methods=['GET'])
def get_problem():
    problem_info = db.session.query(Problem.problem_id, Problem.problemName).all()
    return {
        'result': 'success',
        'data': {
            'problem_info': problem_info,
        }
    }, 200

# TODO Default DateTime

class rank_person:
    def __init__(self, uid, username, penalty, AC_num, problems):
        self.uid = uid
        self.user_name = username
        self.penalty = penalty
        self.AC_num = AC_num
        self.problems = problems
    
    def __lt__(self, other):
        if self.AC_num == other.AC_num:
            return self.penalty < other.penalty
        return self.AC_num > other.AC_num
    
    
@contest_page.route('/contest/getrank/<int:cid>', methods=['GET'])
def get_rank(cid):

    rank_dict = {}

    contest_info = db.session.query(Contest.paticipant, Contest.problem_id, Contest.start_time)\
                            .filter(Contest.contest_id == cid)\
                            .first()

    contest_starttime = dt.datetime.strptime(str(contest_info.start_time), '%Y-%m-%d %H:%M:%S')

    contest_pro = contest_info.problem_id.strip(',').split(',')

    contest_par = contest_info.paticipant.strip(',').split(',')

    for i in range(len(contest_par)):
        participant = contest_par[i]
        problem_dict = {}

        for i in range(len(contest_pro)):
            problem_dict[int(contest_pro[i])] = {
                'AC_time': '-1',
                'Wrong_num': 0
            }

        rank_dict[int(participant)] = {
            'user_name':'',
            'penalty': 0,
            'AC_num': 0,
            'problems':problem_dict,
        }

    user_list = Account.query.all()
    
    for i in user_list:
        if i.uid in rank_dict:
            rank_dict[i.uid]['user_name'] = i.username


    sub_list = Submission.query
    sub_list = sub_list.filter(Submission.for_test == cid)\
                        .order_by(Submission.submit_id)\
                        .all()

    for sub in sub_list:
        if rank_dict[sub.account_id]['problems'][sub.problem_id]['AC_time'] == '-1':
            if sub.result == 'AC':
                sub_datetime = dt.datetime.strptime(str(sub.time), '%Y-%m-%d %H:%M:%S')
                rank_dict[sub.account_id]['problems'][sub.problem_id]['AC_time'] = (sub_datetime-contest_starttime).seconds//60
                rank_dict[sub.account_id]['penalty'] = (sub_datetime-contest_starttime).seconds//60 + rank_dict[sub.account_id]['problems'][sub.problem_id]['Wrong_num']*20
                rank_dict[sub.account_id]['AC_num'] += 1
            else:
                rank_dict[sub.account_id]['problems'][sub.problem_id]['Wrong_num'] += 1

    
    rank_dict = sorted(sorted(rank_dict.items(), key = lambda x : getitem(x[1],'AC_num'), reverse=False), key = lambda x : getitem(x[1],'penalty'), reverse=True)

    rank_list = []

    for person in rank_dict:
        rank_list.append(rank_person(person[0], person[1]['user_name'], person[1]['penalty'], person[1]['AC_num'], person[1]['problems']))
    
    rank_list.sort();
    print(type(rank_list))
    for i in rank_list:
        print(i)

    rank_info = []

    for i in range(len(rank_list)):
        rank_info.append({
            'user_name': rank_list[i].user_name,
            'penalty': rank_list[i].penalty,
            'AC_num': rank_list[i].AC_num,
            'problems': rank_list[i].problems,
        })

    return {
        'result': 'success',
        'data': rank_info
        }

@contest_page.route('/contest/setproblem/<int:cid>', methods=['GET', 'POST'])
def set_problem(cid):
    print('setproblem:', request.method)
    problem_list = (db.session.query(Contest.problem_id).filter(Contest.contest_id == cid).first().problem_id).strip(',').split(',')
    problem_info = []

    for pid in problem_list:
        problem = Problem.query.filter_by(problem_id=pid).first()
        info = json.loads(problem.info)

        problem_info.append({
            'pid': pid,
            'problem_name': problem.problemName,
            'info': info
        })

    return {
        'result': 'success',
        'data': problem_info
        }