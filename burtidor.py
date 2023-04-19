import asyncio
import os
from tkinter import (
    Button, Entry, HORIZONTAL, Label, Scale, Tk,
    filedialog, messagebox, Canvas
)
import threading
import simpleaudio as sa
from pydub import AudioSegment
import numpy as np
from PIL import Image, ImageTk


def apply_lowpass_filter(audio, cutoff_frequency):
    return audio.low_pass_filter(cutoff_frequency)


def apply_highpass_filter(audio, cutoff_frequency):
    return audio.high_pass_filter(cutoff_frequency)


class AudioEditorGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("BURT_AUDIO")
        self.audio = None
        self.original_audio = None
        self.playback = None
        self.playing = False
        self.playback_position = 0
        self.waveform_update_interval = 50

        # UI components
        self.open_button = Button(master, text="Open", command=self.open_file)
        self.open_button.grid(row=0, column=0)

        self.save_button = Button(master, text="Save", command=self.save_file)
        self.save_button.grid(row=0, column=1)

        self.play_button = Button(master, text="Play", command=self.play_audio)
        self.play_button.grid(row=1, column=0)

        self.stop_button = Button(master, text="Stop", command=self.stop_audio)
        self.stop_button.grid(row=1, column=1)

        self.lowpass_label = Label(master, text="Low-pass Filter")
        self.lowpass_label.grid(row=2, column=0)

        self.lowpass_fader = Scale(master, from_=1, to=20000, orient=HORIZONTAL, command=self.update_lowpass)
        self.lowpass_fader.grid(row=2, column=1)

        self.lowpass_entry = Entry(master, width=8)
        self.lowpass_entry.grid(row=2, column=2)
        self.lowpass_entry.insert(0, "20000")
        self.lowpass_entry.bind('<Return>', self.set_lowpass_from_entry)

        self.highpass_label = Label(master, text="High-pass Filter")
        self.highpass_label.grid(row=3, column=0)

        self.highpass_fader = Scale(master, from_=1, to=20000, orient=HORIZONTAL, command=self.update_highpass)
        self.highpass_fader.grid(row=3, column=1)

        self.highpass_entry = Entry(master, width=8)
        self.highpass_entry.grid(row=3, column=2)
        self.highpass_entry.insert(0, "1")
        self.highpass_entry.bind('<Return>', self.set_highpass_from_entry)

        self.volume_label = Label(master, text="Volume (dB)")
        self.volume_label.grid(row=4, column=0)

        self.volume_fader = Scale(master, from_=-20, to=20, orient=HORIZONTAL)
        self.volume_fader.grid(row=4, column=1)

        self.change_volume_button = Button(master, text="Change Volume", command=self.change_volume)
        self.change_volume_button.grid(row=4, column=2)

        self.canvas = Canvas(master, width=400, height=200)
        self.canvas.grid(row=5, column=0, columnspan=4)

    def open_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            asyncio.run(self.load_audio_async(file_path))

    async def load_audio_async(self, file_path):
        loop = asyncio.get_running_loop()
        self.audio = await loop.run_in_executor(None, lambda: AudioSegment.from_file(file_path))
        self.original_audio = self.audio[:len(self.audio)]  # Copy the entire audio segment
        self.display_audio_waveform()

    def display_audio_waveform(self):
        audio_samples = np.frombuffer(self.audio.get_array_of_samples(), dtype=np.int16)
        audio_samples = audio_samples[::self.audio.channels]
        audio_waveform = 1 - np.abs(audio_samples / 2 ** 15)
        waveform_image = Image.fromarray((audio_waveform * 255).astype(np.uint8).reshape(1, -1).repeat(200, axis=0))
        waveform_image = waveform_image.resize((400, 200), Image.LANCZOS)
        waveform_photo = ImageTk.PhotoImage(waveform_image)
        self.canvas.create_image(0, 0, anchor="nw", image=waveform_photo)
        self.canvas.image = waveform_photo

    def save_file(self):
        if self.audio:
            file_path = filedialog.asksaveasfilename()
            if file_path:
                self.audio.export(file_path, format=os.path.splitext(file_path)[1][1:])
        else:
            messagebox.showwarning("Warning", "No audio loaded. Please open an audio file first.")

    def apply_filters(self):
        filtered_audio = self.original_audio
        lowpass_cutoff = self.lowpass_fader.get()
        highpass_cutoff = self.highpass_fader.get()

        filtered_audio = apply_lowpass_filter(filtered_audio, lowpass_cutoff)
        filtered_audio = apply_highpass_filter(filtered_audio, highpass_cutoff)

        return filtered_audio

    def play_audio(self):
        if self.audio:
            if self.playback and self.playback.is_playing():
                self.playback.stop()
            threading.Thread(target=self.play_audio_thread).start()
            self.playing = True
            self.update_waveform_position()
        else:
            messagebox.showwarning("Warning", "No audio loaded. Please open an audio file first.")

    def play_audio_thread(self):
        playback = sa.play_buffer(self.audio.raw_data, num_channels=self.audio.channels, bytes_per_sample=self.audio.sample_width, sample_rate=self.audio.frame_rate)
        self.playback = playback
        self.playing = True
        asyncio.run(self.update_waveform_position())
        playback.wait_done()
        self.playing = False

    def update_waveform_position(self):
        def update_position():
            while self.playing:
                position = self.playback_position / len(self.audio) * 400
                self.canvas.coords(self.waveform_position_line, position, 0, position, 200)
                self.playback_position += 50
                self.master.after(50, update_position)
        threading.Thread(target=update_position).start()

    def set_lowpass_from_entry(self, event):
        value = self.lowpass_entry.get()
        if value.isdigit():
            value = int(value)
            self.lowpass_fader.set(value)
            self.update_lowpass(value, update_entry=False)

    def set_highpass_from_entry(self, event):
        value = self.highpass_entry.get()
        if value.isdigit():
            value = int(value)
            self.highpass_fader.set(value)
            self.update_highpass(value, update_entry=False)

    def update_lowpass(self, value, update_entry=True):
        if self.audio:
            cutoff_frequency = int(value)
            self.audio = apply_lowpass_filter(self.original_audio, cutoff_frequency)
            if update_entry:
                self.lowpass_entry.delete(0, 'end')
                self.lowpass_entry.insert(0, str(value))
        else:
            messagebox.showwarning("Warning", "No audio loaded. Please open an audio file first.")

    def change_volume(self):
        if self.audio:
            volume_change = self.volume_fader.get()
            self.audio += volume_change
        else:
            messagebox.showwarning("Warning", "No audio loaded. Please open an audio file first.")

    def update_highpass(self, value, update_entry=True):
        if self.audio:
            cutoff_frequency = int(value)
            self.audio = apply_highpass_filter(self.original_audio, cutoff_frequency)
            if update_entry:
                self.highpass_entry.delete(0, 'end')
                self.highpass_entry.insert(0, str(value))
        else:
            messagebox.showwarning("Warning", "No audio loaded. Please open an audio file first.")

    async def update_waveform_position(self):
        self.canvas.delete("playback_line")
        while self.playing:
            position = int(400 * (self.playback_position / len(self.audio)))
            self.canvas.create_line(position, 0, position, 200, fill="red", tags="playback_line")
            self.playback_position += self.waveform_update_interval
            await asyncio.sleep(self.waveform_update_interval / 1000)

    def stop_audio(self):
        if self.playback and self.playback.is_playing():
            self.playback.stop()
            self.playing = False
            self.playback_position = 0
            self.canvas.delete("playback_line")

if __name__ == "__main__":
    root = Tk()
    audio_editor = AudioEditorGUI(root)
    root.mainloop()
