import tkinter as tk
from tkinter import ttk
import ytmusicapi
from ytmusicapi import YTMusic, OAuthCredentials
import os
from dotenv import load_dotenv

global playlists
global ytmusic
global CLIENT_ID
global CLIENT_SECRET

class ScrollableFrame(ttk.Frame):
    # A vertically scrollable frame for holding dynamic widgets.
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


class DynamicGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Youtube Music Playlist Sorter")

        # Main layout: two columns (left = scrollable, right = fixed)
        self.left_frame = ScrollableFrame(root)
        self.left_frame.grid(row=0, column=0, sticky="nsew")

        self.right_frame = ttk.Frame(root)
        self.right_frame.grid(row=0, column=1, sticky="ns", padx=20, pady=20)

        # Row counter for left side
        self.button_row = 0
        self.buttons = []  # Store references to buttons
        
        # Refresh button and debug text on the right side
        self.refresh_button = ttk.Button(self.right_frame, text="Refresh List", command=self.refresh_playlist_list)
        self.refresh_button.pack(pady=10)
        
        self.text_debug = tk.Label(self.right_frame, text='')
        self.text_debug.pack(pady=10)

        # Allow resizing
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(0, weight=1)

    # Adds button to list and GUI
    def add_button(self, btn_text, label_text, command=None):
        frame = ttk.Frame(self.left_frame.scrollable_frame)
        frame.grid(row=self.button_row, column=0, sticky="w", pady=5)

        button = tk.Button(frame, text=btn_text, command=command)
        button.pack(side="left", padx=(0, 10))

        label = ttk.Label(frame, text=label_text)
        label.pack(side="left")

        self.buttons.append(button)
        self.button_row += 1
        
    # Clears all buttons from the left frame
    def clear_buttons(self):
        for widget in self.left_frame.scrollable_frame.winfo_children():
            widget.destroy()
        self.buttons.clear()
        self.button_row = 0
    
    # Refreshes the scrollable playlist list from YouTube Music
    def refresh_playlist_list(self):
        global ytmusic
        try:
            ytmusic = YTMusic('oauth.json', oauth_credentials=OAuthCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET))
            playlists = ytmusic.get_library_playlists(limit=None)
            if not playlists:
                self.text_debug.config(text="No playlists found or error accessing YouTube Music.")
                return
            self.clear_buttons()
            for pl in playlists:
                if not pl.get("ownPlaylist", True):
                    continue
                if pl["title"].lower() == "liked music":
                    continue
                self.add_button("Sort", pl['title'], command=lambda pid=pl["playlistId"]: self.sort_playlist(pid))
                self.set_active_state()
        except Exception as e:
            self.text_debug.config(text="Error loading playlists, check console for details.")
            print(f"Error loading playlists: {e}")
        
    # Sorts a playlist by artist name A-Z, with backup and safe reordering
    def sort_playlist(self, pid):
        self.set_busy_state()

        try:
            playlist = ytmusic.get_playlist(pid, limit=None)
            tracks = playlist.get("tracks", [])
            if not tracks:
                self.set_active_state()
                return
        except Exception as e:
            self.text_debug.config(text="Error getting playlist, check console for details.")
            print(f"Error getting playlist: {e}")
            self.set_active_state()
            return

        # Create backup of selected playlist
        backup_pid = None
        try:
            backup_pid = ytmusic.create_playlist(
                title=f"Backup of {playlist['title']}",
                description="Temporary backup for sorting",
                privacy_status="PRIVATE"
            )
            video_ids = [t["videoId"] for t in tracks if t.get("videoId")]
            if video_ids:
                ytmusic.add_playlist_items(backup_pid, video_ids)
        except Exception as e:
            self.text_debug.config(text="Error creating backup playlist.")
            print(f"Error creating backup: {e}")
            self.set_active_state()
            return

        # Sort tracks by artist name
        sorted_tracks = sorted(tracks, key=lambda t: (t["artists"][0]["name"].lower() if t.get("artists") else ""))
        sorted_video_ids = [t["videoId"] for t in sorted_tracks if t.get("videoId")]
        failed_sort = False

        # Try to reorder tracks in the original playlist
        try:
            ytmusic.remove_playlist_items(pid, [
                {"videoId": t["videoId"], "setVideoId": t["setVideoId"]}
                for t in tracks if t.get("videoId") and t.get("setVideoId")
            ])
            if sorted_video_ids:
                ytmusic.add_playlist_items(pid, sorted_video_ids)
        except Exception as e:
            failed_sort = True
            self.text_debug.config(text="Error sorting playlist, restoring backup.")
            print(f"Error sorting playlist: {e}")
            # Restore from backup
            try:
                ytmusic.remove_playlist_items(pid, [
                    {"videoId": t["videoId"], "setVideoId": t["setVideoId"]}
                    for t in tracks if t.get("videoId") and t.get("setVideoId")
                ])
                ytmusic.add_playlist_items(pid, video_ids)
            except Exception as restore_e:
                self.text_debug.config(text="Error restoring from backup, check console for details.")
                print(f"Error restoring from backup: {restore_e}\nManual fix may be required.")
                self.set_active_state()
                return

        # Delete backup playlist
        try:
            ytmusic.delete_playlist(backup_pid)
        except Exception as e:
            print(f"Warning: could not delete backup playlist: {e}")

        if failed_sort:
            self.text_debug.config(text="Error sorting playlist, restored from backup.")
        else:
            self.text_debug.config(text="Sorted playlist successfully.")
        self.set_active_state()
    
    def set_buttons_state(self, state):
        for btn in self.buttons:
            btn.config(state=state)

    def set_button_color(self, bg, fg="black"):
        for btn in self.buttons:
            btn.config(bg=bg, fg=fg)
            
    def set_busy_state(self):
        self.set_button_color("red", "black")
        self.set_buttons_state("disabled")
        
    def set_active_state(self):
        self.set_button_color("green", "black")
        self.set_buttons_state("normal")

# Start UI
if __name__ == "__main__":
    load_dotenv()
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Missing CLIENT_ID or CLIENT_SECRET — set them in env or .env")
        exit(1)
    
    root = tk.Tk()
    gui = DynamicGUI(root)
    gui.refresh_playlist_list()
    gui.set_active_state()
    root.mainloop()