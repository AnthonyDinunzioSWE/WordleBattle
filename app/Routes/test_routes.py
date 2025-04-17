import os
from flask import Blueprint, render_template, redirect, url_for, session, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from ..Models.models import User, db
from flask_socketio import emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from ..Instances.instances import socketio
from flask_dance.contrib.google import google
import random

test_bp = Blueprint('test', __name__)

@test_bp.route('/update_rank/bronze')
def update_rank_bronze():
    user = User.query.get(current_user.id)
    print(f"Updating rank to Bronze for user: {current_user.username}")
    user.elo_rating = 500
    print(f"UPDATED ELO: {user.elo_rating}")
    return redirect(url_for('main.profile'))

@test_bp.route('/update_rank/silver')
def update_rank_silver():
    user = User.query.get(current_user.id)
    user.elo_rating = 900
    return redirect(url_for('main.profile'))

@test_bp.route('/update_rank/gold')
def update_rank_gold():
    user = User.query.get(current_user.id)
    user.elo_rating = 1500
    return redirect(url_for('main.profile'))

@test_bp.route('/update_rank/platinum')
def update_rank_platinum():
    user = User.query.get(current_user.id)
    user.elo_rating = 2000
    return redirect(url_for('main.profile'))

@test_bp.route('/update_rank/diamond')
def update_rank_diamond():
    user = User.query.get(current_user.id)
    user.elo_rating = 2500
    return redirect(url_for('main.profile'))
