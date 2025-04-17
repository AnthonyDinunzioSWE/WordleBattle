import os
from flask import Blueprint, render_template, redirect, url_for, session, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from ..Models.models import User, db
from flask_socketio import emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from ..Instances.instances import socketio
from flask_dance.contrib.google import google
import random

main = Blueprint('main', __name__)
queue = []
game_rooms = {}

def update_elo(player1, player2, result):
    """
    Updates the ELO ratings for two players based on the game result, with additional mechanics for streaks and rank bonuses.

    :param player1: The first player (User object).
    :param player2: The second player (User object).
    :param result: The result of the game. 'player1' if player1 wins, 'player2' if player2 wins, or 'draw'.
    """
    base_k = 32  # Base K-factor, determines the maximum rating change per game

    # Adjust K-factor based on player ranks (higher ranks have higher stakes)
    rank_multiplier = {
        'Bronze': 1.0,
        'Silver': 1.1,
        'Gold': 1.2,
        'Platinum': 1.3,
        'Diamond': 1.5
    }
    k1 = base_k * rank_multiplier.get(player1.rank, 1.0)
    k2 = base_k * rank_multiplier.get(player2.rank, 1.0)

    # Calculate expected scores
    expected_score1 = 1 / (1 + 10 ** ((player2.elo_rating - player1.elo_rating) / 400))
    expected_score2 = 1 / (1 + 10 ** ((player1.elo_rating - player2.elo_rating) / 400))

    # Determine actual scores
    if result == 'player1':
        actual_score1 = 1
        actual_score2 = 0
        player1.streak += 1
        player2.streak = 0
    elif result == 'player2':
        actual_score1 = 0
        actual_score2 = 1
        player2.streak += 1
        player1.streak = 0
    else:  # Draw
        actual_score1 = 0.5
        actual_score2 = 0.5
        player1.streak = 0
        player2.streak = 0

    # Bonus for win streaks
    streak_bonus = 5  # Additional ELO points for each win in a streak
    if player1.streak > 1:
        k1 += streak_bonus
    if player2.streak > 1:
        k2 += streak_bonus

    # Update ELO ratings
    player1.elo_rating += int(k1 * (actual_score1 - expected_score1))
    player2.elo_rating += int(k2 * (actual_score2 - expected_score2))

    # Update highest streaks
    player1.highest_streak = max(player1.highest_streak, player1.streak)
    player2.highest_streak = max(player2.highest_streak, player2.streak)

    # Print updated ELO for debugging
    print(f"Updated ELO: {player1.username} -> {player1.elo_rating}, {player2.username} -> {player2.elo_rating}")
    print(f"Streaks: {player1.username} -> {player1.streak}, {player2.username} -> {player2.streak}")
    
@main.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.profile"))
    else:
        session.clear()
    return render_template("index.html")

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash('Email already registered.', 'danger')
            return redirect(url_for('main.register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('main.login'))

    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('main.profile'))
        flash('Invalid email or password.', 'danger')

    return render_template('login.html')

@main.route("/google/authorized")
def google_authorized():
    print("Entering google_authorized route")  # Debugging log
    print(f"Google authorized: {google.authorized}")  # Debugging log
    print(f"Google token: {google.token}")  # Debugging log

    if not google.authorized:
        print("Google not authorized")  # Debugging log
        flash("Google login failed. Please try again.", "danger")
        return redirect(url_for("main.login"))

    # Get user info from Google
    response = google.get("/oauth2/v2/userinfo")
    if not response.ok:
        flash("Failed to fetch user info from Google.", "danger")
        return redirect(url_for("main.login"))

    user_info = response.json()
    print(f"User info: {user_info}")  # Debugging log

    # Check if user exists
    user = User.query.filter_by(email=user_info["email"]).first()
    if not user:
        print("Creating new user")  # Debugging log
        user = User(
            username=user_info["name"],
            email=user_info["email"],
            google_id=user_info["id"],
            profile_picture=user_info.get("picture", "default.jpg"),
        )
        db.session.add(user)
        db.session.commit()

    # Log in the user
    login_user(user)
    print("User logged in successfully")  # Debugging log
    flash("Logged in successfully!", "success")
    return redirect(url_for("main.profile"))

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@main.route('/profile')
@login_required
def profile():
    print(f"Current User Profile Image URI: {current_user.profile_picture}")
    return render_template('profile.html', user=current_user)


@main.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    if 'profile_picture' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('main.profile'))

    file = request.files['profile_picture']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('main.profile'))

    filename = f"{current_user.id}.jpg"
    filepath = os.path.join('app/static/profile_images', filename)
    file.save(filepath)

    current_user.profile_picture = f"profile_images/{filename}"
    db.session.commit()
    flash('Profile picture updated!', 'success')
    return redirect(url_for('main.profile'))

@main.route('/find_match')
@login_required
def find_match():
    return render_template('waiting.html')

@main.route('/game_results')
@login_required
def game_results():
    result = request.args.get('result', 'Game over!')
    player1 = request.args.get('player1', '')
    player2 = request.args.get('player2', '')
    player1_elo_change = request.args.get('player1_elo_change', 0, type=int)
    player2_elo_change = request.args.get('player2_elo_change', 0, type=int)
    user = current_user  # Get the logged-in user's data

    print(f"ELO Change for player1: {player1_elo_change}")
    print(f"ELO Change for player2: {player2_elo_change}")

    return render_template(
        'game_results.html',
        result=result,
        user=user,
        player1=player1,
        player2=player2,
        player1_elo_change=player1_elo_change,
        player2_elo_change=player2_elo_change
    )

@main.route('/game_room/<room>')
@login_required
def game_room(room):
    if room not in game_rooms:
        flash("Game room not found. Please requeue.", "danger")
        return redirect(url_for("main.find_match"))

    # Retrieve player details
    player1_username = game_rooms[room]['player1']
    player2_username = game_rooms[room]['player2']

    # Fetch player details from the database
    player1 = User.query.filter_by(username=player1_username).first()
    player2 = User.query.filter_by(username=player2_username).first()

    if not player1 or not player2:
        flash("Player details not found. Please requeue.", "danger")
        return redirect(url_for("main.find_match"))

    return render_template(
        'game_room.html',
        room=room,
        player1=player1,
        player2=player2
    )


@socketio.on('join')
def on_join(data):
    room = data
    join_room(room)
    emit('message', f'{current_user.username} has joined the room.', to=room)

@socketio.on('chat')
def on_chat(data):
    room = data['room']
    message = data['message']
    emit('message', f'{current_user.username}: {message}', to=room)

@socketio.on('join_queue')
def on_join_queue():
    global queue
    sid = request.sid  # Get the Socket.IO session ID
    username = current_user.username  # Get the current user's username

    # Check if the player is already in the queue
    for user, user_sid in queue:
        if user == username:
            print(f"Player {username} is already in the queue.")
            return

    # Add the player to the queue
    queue.append((username, sid))
    print(f"Player {username} joined the queue. Queue size: {len(queue)}")

    # Check if there are enough players to start a match
    if len(queue) >= 2:
        # Pop two players from the queue
        (player1, sid1) = queue.pop(0)
        (player2, sid2) = queue.pop(0)
        room = f"room-{random.randint(1000, 9999)}"

        # Initialize the game room
        game_rooms[room] = {
            'player1': player1,
            'player2': player2,
            'player1_sid': sid1,
            'player2_sid': sid2,
            'player1_word': None,
            'player2_word': None,
            'player1_guesses': [],
            'player2_guesses': [],
            'winner': None,
            'phase': 'picking'
        }

        # Notify both players to join the game room
        emit('match_found', {'room': room, 'player1': player1, 'player2': player2}, to=sid1)
        emit('match_found', {'room': room, 'player1': player1, 'player2': player2}, to=sid2)

        print(f"Match created: {player1} vs {player2} in room {room}")

@socketio.on('start_game')
def start_game(data):
    room = data['room']
    player1 = data['player1']
    player2 = data['player2']

    # Retrieve SIDs from the game room
    player1_sid = game_rooms[room].get('player1_sid')
    player2_sid = game_rooms[room].get('player2_sid')

    if not player1_sid or not player2_sid:
        print(f"Error: Could not find SID for one or both players ({player1}, {player2})")
        return

    # Notify players to start the picking phase
    emit('start_picking_phase', {'room': room}, to=player1_sid)
    emit('start_picking_phase', {'room': room}, to=player2_sid)

@socketio.on('submit_word')
def submit_word(data):
    room = data['room']
    word = data['word']
    username = current_user.username

    if room not in game_rooms:
        print(f"Error: Room {room} not found in game_rooms")
        return

    # Store the submitted word
    if game_rooms[room]['player1'] == username:
        game_rooms[room]['player1_word'] = word
        emit('opponent_locked_in', to=game_rooms[room]['player2_sid'])
    elif game_rooms[room]['player2'] == username:
        game_rooms[room]['player2_word'] = word
        emit('opponent_locked_in', to=game_rooms[room]['player1_sid'])

    # Check if both players have submitted their words
    if game_rooms[room]['player1_word'] and game_rooms[room]['player2_word']:
        start_guessing_phase(room)

@socketio.on('timeout_picking_phase')
def timeout_picking_phase(data):
    room = data['room']

    if room not in game_rooms:
        print(f"Error: Room {room} not found in game_rooms")
        return

    # Assign random words if players didn't submit
    if not game_rooms[room]['player1_word']:
        game_rooms[room]['player1_word'] = get_random_word()
    if not game_rooms[room]['player2_word']:
        game_rooms[room]['player2_word'] = get_random_word()

    start_guessing_phase(room)

@socketio.on('submit_guess')
def submit_guess(data):
    room = data['room']
    guess = data['guess'].lower()  # Convert the guess to lowercase
    username = current_user.username

    print(f"Received guess from {username} in room {room}: {guess}")  # Debugging log

    if room not in game_rooms:
        print(f"Error: Room {room} not found in game_rooms")
        return

    # Determine the opponent's word
    if game_rooms[room]['player1'] == username:
        opponent_word = game_rooms[room]['player2_word'].lower()  # Convert opponent's word to lowercase
        game_rooms[room]['player1_guesses'].append(guess)
    elif game_rooms[room]['player2'] == username:
        opponent_word = game_rooms[room]['player1_word'].lower()  # Convert opponent's word to lowercase
        game_rooms[room]['player2_guesses'].append(guess)
    else:
        print(f"Error: Username {username} not found in room {room}")
        return

    # Generate feedback for the guess
    feedback = []
    for i in range(len(guess)):
        if guess[i] == opponent_word[i]:
            feedback.append('green')  # Correct letter in the correct position
        elif guess[i] in opponent_word:
            feedback.append('yellow')  # Correct letter in the wrong position
        else:
            feedback.append('gray')  # Incorrect letter

    print(f"Generated feedback for guess: {feedback}")  # Debugging log

    # Send feedback to the client
    emit('guess_feedback', {'guess': guess.upper(), 'feedback': feedback}, to=request.sid)

    # Check if the guess is correct
    if guess == opponent_word:
        game_rooms[room]['winner'] = 'player1' if game_rooms[room]['player1'] == username else 'player2'
        end_game(room)
        return

    # Check for draw condition
    if len(game_rooms[room]['player1_guesses']) >= 6 and len(game_rooms[room]['player2_guesses']) >= 6:
        game_rooms[room]['winner'] = None  # No winner
        end_game(room)

def end_game(room):
    # Determine winner and update stats
    winner = game_rooms[room]['winner']
    player1_username = game_rooms[room]['player1']
    player2_username = game_rooms[room]['player2']

    player1 = User.query.filter_by(username=player1_username).first()
    player2 = User.query.filter_by(username=player2_username).first()

    # Store initial ELO ratings
    initial_elo_player1 = player1.elo_rating
    initial_elo_player2 = player2.elo_rating

    if winner == 'player1':
        result = 'player1'
        player1.wins += 1
        player2.losses += 1
        update_elo(player1, player2, 'player1')
    elif winner == 'player2':
        result = "player2"
        player2.wins += 1
        player1.losses += 1
    else:
        result = "draw"
        player1.draws += 1
        player2.draws += 1

    # Update stats in the database
    player1.games_played += 1
    player2.games_played += 1
    player1.update_rank()
    player2.update_rank()
    db.session.commit()

    print(f"Initial ELO for {player1.username}: {initial_elo_player1}")
    print(f"Initial ELO for {player2.username}: {initial_elo_player2}")

    update_elo(player1, player2, result)

    print(f"Updated ELO for {player1.username}: {player1.elo_rating}")
    print(f"Updated ELO for {player2.username}: {player2.elo_rating}")

    # Calculate ELO changes after committing the session
    elo_change_player1 = player1.elo_rating - initial_elo_player1
    elo_change_player2 = player2.elo_rating - initial_elo_player2

    print(f"ELO Change for {player1.username}: {elo_change_player1}")
    print(f"ELO Change for {player2.username}: {elo_change_player2}")

    # Notify players of the result
    emit('game_over', {
        'result': result,
        'player1': player1.username,
        'player2': player2.username,
        'player1_elo_change': elo_change_player1,
        'player2_elo_change': elo_change_player2
    }, to=room)

    # Clean up game state
    del game_rooms[room]

def get_random_word():
    # Return a random 5-letter word
    words = ['apple', 'grape', 'peach', 'mango', 'berry']
    return random.choice(words)

def start_guessing_phase(room):
    if room not in game_rooms:
        print(f"Error: Room {room} not found in game_rooms during start_guessing_phase")
        return

    # Move to the guessing phase
    game_rooms[room]['phase'] = 'guessing'
    game_rooms[room]['player1_guesses'] = []  # Ensure no guesses are pre-filled
    game_rooms[room]['player2_guesses'] = []  # Ensure no guesses are pre-filled

    print(f"Starting guessing phase for room {room}")
    emit('start_guessing_phase', {
        'room': room,
        'opponent_word_length': len(game_rooms[room]['player1_word'])
    }, to=room)