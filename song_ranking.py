import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import json
import os
import time
from datetime import datetime

def initialize_spotify():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=st.secrets["spotify"]["client_id"],
        client_secret=st.secrets["spotify"]["client_secret"],
        redirect_uri=st.secrets["spotify"]["redirect_uri"],
        scope='user-top-read user-library-read user-read-recently-played playlist-read-private'
    ))

def get_spotify_suggestions(sp):
    suggestions = []
    
    try:
        # Get top tracks with time range info
        print("Fetching top tracks...")
        top_tracks = sp.current_user_top_tracks(limit=50, time_range='long_term')['items']
        
        # Get recently played tracks with play counts
        print("Fetching recent tracks...")
        recent_tracks = sp.current_user_recently_played(limit=50)['items']
        
        # Get play count for last year
        now = int(time.time() * 1000)  # Current time in milliseconds
        year_ago = now - (365 * 24 * 60 * 60 * 1000)  # 365 days ago in milliseconds
        
        # Count plays in the last year from recent plays
        play_counts = {}
        for item in recent_tracks:
            track_id = item['track']['id']
            played_at = int(datetime.strptime(item['played_at'], '%Y-%m-%dT%H:%M:%S.%fZ').timestamp() * 1000)
            if played_at > year_ago:
                play_counts[track_id] = play_counts.get(track_id, 0) + 1

        # Combine and deduplicate suggestions
        seen_ids = set()
        
        for track in top_tracks:
            if track['id'] not in seen_ids:
                image_url = track['album']['images'][0]['url'] if track['album']['images'] else None
                release_year = track['album']['release_date'][:4]  # Get year from release date
                suggestions.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'full_name': f"{track['name']} - {track['artists'][0]['name']}",
                    'image_url': image_url,
                    'release_year': release_year,
                    'play_count': play_counts.get(track['id'], 0)
                })
                seen_ids.add(track['id'])
        
        return suggestions
        
    except Exception as e:
        print(f"Error getting suggestions: {str(e)}")
        return []

def search_spotify(sp, query):
    if not query:
        return []
    
    results = sp.search(q=query, type='track', limit=10)
    return [{
        'id': track['id'],
        'name': track['name'],
        'artist': track['artists'][0]['name'],
        'full_name': f"{track['name']} - {track['artists'][0]['name']}",
        'image_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
        'release_year': track['album']['release_date'][:4]  # Get year from release date
    } for track in results['tracks']['items']]

def display_song(song, rank=None):
    """Display song information with image inline and additional info"""
    spotify_url = f"https://open.spotify.com/track/{song['id']}"
    
    # Create display text with year, handling missing release_year
    release_year = song.get('release_year', 'N/A')
    display_text = f"{song['full_name']} ({release_year})"
    if rank is not None:
        display_text = f"{rank}. {display_text}"
    
    html = f'''
        <div style="display: flex; align-items: center; gap: 10px; height: 40px;">
            <a href="{spotify_url}" target="_blank" style="display: flex; align-items: center; gap: 10px; text-decoration: none; color: #191414;">
                <img src="{song['image_url']}" style="width: 30px; height: 30px;">
                <p style="margin: 0; font-size: 16px;">{display_text}</p>
            </a>
        </div>
    '''
    st.markdown(html, unsafe_allow_html=True)

def move_to_position(songs, old_idx, new_idx):
    """Move a song from one position to another, shifting other songs accordingly"""
    if 0 <= new_idx < len(songs):
        song = songs.pop(old_idx)
        songs.insert(new_idx, song)
        return True
    return False

def get_next_available_rank(ranked_songs):
    """Find the lowest available rank that isn't taken"""
    if not ranked_songs:
        return 1
    
    # Get all current ranks
    current_ranks = {song['rank'] for song in ranked_songs}
    
    # Find the first number from 1 to 2000 that's not in current_ranks
    for rank in range(1, 2001):
        if rank not in current_ranks:
            return rank
    
    return 2000  # Fallback to 2000 if somehow all ranks are taken

def save_rankings(rankings):
    """Save rankings to a JSON file"""
    with open('rankings.json', 'w') as f:
        json.dump(rankings, f)

def load_rankings():
    """Load rankings from JSON file and ensure all required fields are present"""
    if os.path.exists('rankings.json'):
        with open('rankings.json', 'r') as f:
            rankings = json.load(f)
            
            # Update any existing songs that might not have release_year
            for song in rankings:
                if 'release_year' not in song:
                    try:
                        track = st.session_state.spotify.track(song['id'])
                        song['release_year'] = track['album']['release_date'][:4]
                    except:
                        song['release_year'] = 'N/A'
            
            return rankings
    return []

def main():
    # Set page config with custom background and text colors
    st.set_page_config(page_title="Top 2000 Adinde (van Stijn weet je wel)", layout="wide")

    # Custom CSS for styling
    st.markdown("""
        <style>
            /* Main background */
            .stApp {
                background-color: #1db954;
            }
            
            /* Text color */
            .stMarkdown, .stText, p, h1, h2, h3 {
                color: #191414 !important;
            }
            
            /* Button styling */
            .stButton button {
                background-color: white !important;
                color: #191414 !important;
                border: none;
                height: 38px;
                padding: 0 16px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                min-width: 0;
            }
            
            /* Button hover effect */
            .stButton button:hover {
                background-color: #f0f0f0 !important;
                color: #191414 !important;
                border: none;
            }
            
            /* Input fields */
            .stNumberInput input {
                color: #191414;
                background-color: white;
                height: 38px;
                width: 80px !important;
            }
            
            /* Success messages */
            .stSuccess {
                background-color: white;
                color: #191414;
            }

            /* Column alignment */
            [data-testid="column"] {
                display: flex;
                align-items: center;
                gap: 1rem;
                min-width: 0;
            }

            /* Number input container */
            .stNumberInput {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                min-width: 0;
            }

            /* Number input label */
            .stNumberInput label {
                margin-bottom: 0 !important;
                font-size: 14px;
                min-height: 0 !important;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            /* Adjust width of number input wrapper */
            [data-testid="stNumberInput"] {
                width: auto !important;
                min-width: 0;
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("Top 2000 Adinde (van Stijn weet je wel)")

    # Initialize session state
    if 'ranked_songs' not in st.session_state:
        st.session_state.ranked_songs = load_rankings()  # Load saved rankings
    if 'spotify' not in st.session_state:
        try:
            st.session_state.spotify = initialize_spotify()
        except Exception as e:
            st.error(f"Failed to connect to Spotify: {str(e)}")
            return
    if 'suggestions' not in st.session_state:
        st.session_state.suggestions = []

    # Create two columns with [3, 2] ratio (60% - 40%)
    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.subheader(f"Your Rankings ({len(st.session_state.ranked_songs)} songs ranked)")
        
        if st.session_state.ranked_songs:
            # Display songs directly without sorting functionality
            for idx, song in enumerate(st.session_state.ranked_songs):
                col1, col2, col3 = st.columns([4, 2, 1])
                with col1:
                    display_song(song, song['rank'])
                with col2:
                    new_rank = st.number_input(
                        "",
                        min_value=1,
                        max_value=2000,
                        value=song['rank'],
                        key=f"rank_{song['id']}_{idx}",
                        label_visibility="collapsed"
                    )
                    if new_rank != song['rank']:
                        song['rank'] = new_rank
                        st.session_state.ranked_songs = sorted(
                            st.session_state.ranked_songs,
                            key=lambda x: x['rank']
                        )
                        save_rankings(st.session_state.ranked_songs)
                        st.rerun()
                with col3:
                    if st.button("Remove", key=f"remove_{song['id']}_{idx}"):
                        st.session_state.ranked_songs.remove(song)
                        save_rankings(st.session_state.ranked_songs)
                        st.rerun()

    with right_col:
        st.subheader("Add Songs")
        
        # Search functionality
        search_query = st.text_input("Search for songs")
        if search_query:
            search_results = search_spotify(st.session_state.spotify, search_query)
            if search_results:
                st.write("Search Results:")
                for idx, song in enumerate(search_results):
                    col1, col2, col3 = st.columns([4, 2, 1])
                    with col1:
                        display_song(song)
                    with col2:
                        next_rank = get_next_available_rank(st.session_state.ranked_songs)
                        rank = st.number_input(
                            "",
                            min_value=1,
                            max_value=2000,
                            value=next_rank,
                            key=f"pos_{song['id']}_{idx}",
                            label_visibility="collapsed"
                        )
                    with col3:
                        if st.button("Add", key=f"add_search_{song['id']}_{idx}"):
                            if song not in st.session_state.ranked_songs:
                                song['rank'] = rank
                                st.session_state.ranked_songs.append(song)
                                st.session_state.ranked_songs = sorted(
                                    st.session_state.ranked_songs,
                                    key=lambda x: x['rank']
                                )
                                save_rankings(st.session_state.ranked_songs)
                                st.success(f"Song added at rank {rank}!")
                                st.rerun()

        # Suggestions section
        st.subheader("Suggestions from your Spotify")
        if st.button("Load Suggestions"):
            suggestions = get_spotify_suggestions(st.session_state.spotify)
            if suggestions:
                st.session_state.suggestions = suggestions
                st.success(f"Loaded {len(suggestions)} suggestions!")
            else:
                st.error("No suggestions found")
            
        if st.session_state.suggestions:
            st.write("Your Top Songs:")
            for idx, song in enumerate(st.session_state.suggestions):
                col1, col2, col3 = st.columns([4, 2, 1])
                with col1:
                    display_song(song)
                with col2:
                    next_rank = get_next_available_rank(st.session_state.ranked_songs)
                    rank = st.number_input(
                        "",
                        min_value=1,
                        max_value=2000,
                        value=next_rank,
                        key=f"pos_sug_{song['id']}_{idx}",
                        label_visibility="collapsed"
                    )
                with col3:
                    if st.button("Add", key=f"add_suggestion_{song['id']}_{idx}"):
                        if song not in st.session_state.ranked_songs:
                            song['rank'] = rank
                            st.session_state.ranked_songs.append(song)
                            st.session_state.ranked_songs = sorted(
                                st.session_state.ranked_songs,
                                key=lambda x: x['rank']
                            )
                            save_rankings(st.session_state.ranked_songs)
                            st.success(f"Song added at rank {rank}!")
                            st.rerun()

    # Add export functionality
    if st.session_state.ranked_songs:
        if st.button("Export Rankings"):
            df = pd.DataFrame(st.session_state.ranked_songs)
            st.download_button(
                label="Download Rankings",
                data=df.to_csv(index=False),
                file_name="my_top_2000.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main() 