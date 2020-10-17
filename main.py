import tkinter as tk
from tkinter import ttk
from threading import Thread
import time
from PIL import Image, ImageTk
import numpy as np
import pyaudio


class MainWindow(tk.Tk):
    def __init__(self, win_per_page=5):
        super(MainWindow, self).__init__()
        self.title("Lion Multi Streamer v0.8a")
        self.canvas = tk.Canvas(self, width=800, height=515, bg="#555555")
        self.canvas.pack()
        self.resizable(width=False, height=False)
        self.control_window = ControlWindow(self)
        self.control_window.frame.place(x=10, y=10)
        self.win_per_page = win_per_page
        self.update_delay = 0.25
        self.stream_windows = []
        y_offset = 70
        y_inc = 90
        for i in range(win_per_page):
            s_win = StreamerWindow(self, i)
            s_win.frame.place(x=10, y=y_offset)
            self.stream_windows.append(s_win)
            y_offset += y_inc


class ControlWindow:
    def __init__(self, root):
        self.width = 780
        self.height = 50
        self.root = root
        self.font = ("helvetica", 10)
        self.status = " -W.L-"
        self.current_page = 0
        self.configured_streams = {}
        self.active_streams = []
        self.preview_device = {}

        # Background Frame
        self.frame = tk.Frame(root, width=self.width, height=self.height, bd=10, relief="ridge")

        # Prev Page Button
        self.prev_page_button = tk.Button(self.frame, font=self.font, text="<",
                                          command=lambda: self.show_page(self.current_page - 1))
        self.prev_page_button.place(anchor="center", x=10, rely=0.5, width=20, height=20)

        # Next Page Button
        self.next_page_button = tk.Button(self.frame, font=self.font, text=">",
                                          command=lambda: self.show_page(self.current_page + 1))
        self.next_page_button.place(anchor="center", x=30, rely=0.5, width=20, height=20)

        # Status Label
        self.status_label_var = tk.StringVar()
        self.status_label_var.set(self.status)
        self.status_label = tk.Label(self.frame, font=self.font, bg="#000000", fg="#FFFFFF",
                                     textvariable=self.status_label_var)
        self.status_label.place(anchor="w", x=50, rely=0.5, width=100, height=20)

        self.preview_label = tk.Label(self.frame, font=self.font, text="Preview Device")
        self.preview_label.place(anchor="w", x=160, rely=0.5, width=100, height=20)

        live_audio = pyaudio.PyAudio()
        self.p_dev_list = self.get_device_list(live_audio, "playback")
        self.c_dev_list = self.get_device_list(live_audio, "capture")
        name_list = []
        for dev in self.p_dev_list:
            new_name = str(dev[0]) + ": " + str(dev[1])
            name_list.append(new_name)
        self.preview_box = ttk.Combobox(self.frame, values=name_list, state="readonly", font=self.font)
        self.preview_box.place(anchor="w", x=270, rely=0.5, width=400, height=20)
        self.preview_box.bind("<<ComboboxSelected>>", self.set_preview_device)
        self.preview_thread = None
        self.sid_to_preview = -1

        # Save Button
        self.save_button = tk.Button(self.frame, font=self.font, text="Save",
                                     command=lambda: self.save_to_file())
        self.save_button.place(anchor="w", x=700, rely=0.5, width=40, height=20)

        self.conn_manage_thread = Thread(name="conn_manage_thread", target=self.conn_manage, daemon=True)
        self.conn_manage_thread.start()

    @staticmethod
    def get_device_list(instance, d_type):
        dev_list = []
        host_api_count = instance.get_host_api_count()
        api_info_list = []
        for i in range(host_api_count):
            info = instance.get_host_api_info_by_index(i)
            api_info_list.append(info)
            for dev in range(info["deviceCount"]):
                dev_info = instance.get_device_info_by_host_api_device_index(i, dev)
                if (d_type == "playback" and dev_info["maxOutputChannels"] > 0)\
                        or (d_type == "capture" and dev_info["maxInputChannels"] > 0):
                    dev_list.append([info["name"], dev_info["name"], dev])
        if len(api_info_list) < 1:
            print("No APIs available")
            return []

        return dev_list

    def set_preview_device(self, _event):
        list_index = self.preview_box.current()
        dev_index = self.p_dev_list[list_index][2]
        if self.preview_device and dev_index == self.preview_device["dev_index"]:
            return
        p_out = pyaudio.PyAudio()
        p_out = p_out.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=44100,
            input=False,
            output=True,
            frames_per_buffer=2048,
            # input_device_index=self.input_device_index,
            output_device_index=dev_index
         )
        self.preview_device["dev_index"] = dev_index
        self.preview_device["source"] = p_out
        print("new preview device -", dev_index, self.p_dev_list[list_index][0], self.p_dev_list[list_index][1])
        self.preview_thread = Thread(name="preview_thread", target=self.preview_thread_func,
                                     args=[dev_index, p_out], daemon=True)
        self.preview_thread.start()

    def preview_thread_func(self, dev_index, p_out):
        print("preview thread started for dev", dev_index)
        while self.preview_device["dev_index"] == dev_index:
            if self.sid_to_preview >= 0 and self.configured_streams[self.sid_to_preview]["preview"] is True:
                in_data = self.configured_streams[self.sid_to_preview]["input_buffer"].pop()
                # print(in_data)
                p_out.write(in_data)
            else:
                p_out.write(bytes(2048))
        p_out.close()
        print("preview thread ended for dev", dev_index)

    def save_to_file(self):
        self.status_label_var.set("File Saved")

    def show_page(self, new_page):
        new_page = 0 if new_page < 0 else new_page
        i = 0
        for w in self.root.stream_windows:
            w.s_id = i + (new_page * self.root.win_per_page)
            w.sid_label_var.set(w.s_id)
            if w.s_id in self.configured_streams.keys():
                w.input_box.current(self.configured_streams[w.s_id]["input_list_index"])
                w.output_label_var.set(self.configured_streams[w.s_id]["output_name"])
                if self.configured_streams[w.s_id]["keep"]:
                    w.keep_button.configure(bg="#00FF00")
                else:
                    w.keep_button.configure(bg="#FF0000")
                if self.configured_streams[w.s_id]["active"]:
                    if self.configured_streams[w.s_id]["status"] == "streaming":
                        w.active_button.configure(bg="#00FF00")
                    else:
                        w.active_button.configure(bg="#FFFF00")
                else:
                    w.active_button.configure(bg="#FF0000")
                w.status_label_var.set(self.configured_streams[w.s_id]["status"])
            else:
                w.input_box.set("")
                w.keep_button.configure(bg="#FF0000")
                w.active_button.configure(bg="#FF0000")
                w.status_label_var.set(" - ")
            i += 1
        self.current_page = new_page
        self.status_label_var.set("Page " + str(self.current_page))

    def conn_manage(self):
        while True:
            time.sleep(1)
            for a in self.configured_streams:
                if self.configured_streams[a]["active"] and self.configured_streams[a]["status"] != "streaming":
                    print("connecting", self.configured_streams[a]["input_name"], "and",
                          self.configured_streams[a]["output_name"], "for S_ID", a)
                    act_id = self.create_act_id(a)
                    self.active_streams.append(act_id)
                    stream_thread = Thread(name=str(a) + "_stream",
                                           target=self.stream_thread, args=[a, act_id], daemon=True)
                    stream_thread.start()
                elif self.configured_streams[a]["active"] is False \
                        and self.configured_streams[a]["status"] == "streaming":
                    a_input = self.configured_streams[a]["input_list_index"]
                    a_output = self.configured_streams[a]["output_list_index"]
                    print("disconnecting", self.c_dev_list[a_input][1], "and", a_output, "for S_ID", a)
                    act_id = self.create_act_id(a)
                    self.active_streams.remove(act_id)

    def create_act_id(self, s_id):
        a_in = self.configured_streams[s_id]["input_name"]
        a_out = self.configured_streams[s_id]["output_name"]
        return str(s_id) + "-" + str(a_in) + "-" + str(a_out)

    def stream_thread(self, s_id, act_id):
        print("play thread created for S_ID", s_id, "with act_id", act_id)

        stream = self.configured_streams[s_id]

        s_timer = 0
        s_timer_last = time.time()
        for w in self.root.stream_windows:
            if w.s_id == s_id:
                w.active_button.configure(bg="#00FF00")
                break
        while act_id in self.active_streams:
            stream["status"] = "streaming"
            if stream["output_type"] == "hardware" and len(stream["input_buffer"]) >= 5:
                stream["output_buffer"].append(stream["input_buffer"].pop())
            elif stream["output_type"] == "icecast":
                pass  # TODO: do icecast stuff
            elif stream["output_type"] == "shoutcast":
                pass  # TODO: do shoutcast stuff
            for w in self.root.stream_windows:
                if w.s_id == s_id:
                    s_timer += time.time() - s_timer_last
                    s_timer_last = time.time()
                    w.status_label_var.set("Up - " + str(round(s_timer)) + " secs")
        self.configured_streams[s_id]["status"] = "stopped"
        for w in self.root.stream_windows:
            if w.s_id == s_id:
                w.status_label_var.set(self.configured_streams[s_id]["status"])
        print("closing play_thread for S_ID", s_id)


class StreamerWindow:
    def __init__(self, root, s_id):
        self.width = 780
        self.height = 80
        self.root = root
        self.font = ("helvetica", 10)
        self.s_id = s_id
        self.status = str(s_id)
        self.update_thread = None
        self.vu_level = 1
        self.vu_level_raw = 1

        # Background Frame
        self.frame = tk.Frame(root, width=self.width, height=self.height, bd=10, relief="ridge")

        # input combobox
        name_list = []
        for dev in self.root.control_window.c_dev_list:
            new_name = str(dev[0]) + ": " + str(dev[1])
            name_list.append(new_name)
        self.input_box = ttk.Combobox(self.frame, values=name_list, state="readonly", font=self.font)
        self.input_box.place(anchor="w", x=10, y=15, width=400, height=20)
        self.input_box.bind("<<ComboboxSelected>>", self.set_input_device)

        # preview button
        self.preview_button = tk.Button(self.frame, font=self.font, text="Preview",
                                        command=lambda: self.preview_button_func(self.s_id))
        self.preview_button.place(anchor="w", x=420, y=15, width=50, height=20)

        # output Label
        self.output_label_var = tk.StringVar()
        self.output_label_var.set("output string")
        self.output_label = tk.Label(self.frame, font=self.font, bg="#000000", fg="#FFFFFF",
                                     textvariable=self.output_label_var)
        self.output_label.place(anchor="w", x=10, y=35, width=400, height=15)

        # output config button
        self.output_config_button = tk.Button(self.frame, font=self.font, text="Config",
                                              command=lambda: self.output_config_button_func(self.s_id))
        self.output_config_button.place(anchor="w", x=420, y=35, width=50, height=20)

        # Output VU Meter
        self.volume_image = self.get_volume_image(True)
        self.volume_image_display = tk.Label(self.frame, image=self.volume_image)
        self.volume_image_display.place(x=750, y=0, width=10, height=60)

        # Stream ID Label
        self.sid_label_var = tk.StringVar()
        self.sid_label_var.set(str(s_id))
        self.sid_label = tk.Label(self.frame, font=self.font, bg="#000000", fg="#FFFFFF",
                                  textvariable=self.sid_label_var)
        self.sid_label.place(anchor="w", x=10, y=55, width=20, height=15)

        # Status Label
        self.status_label_var = tk.StringVar()
        self.status_label_var.set(str(s_id))
        self.status_label = tk.Label(self.frame, font=self.font, bg="#000000", fg="#FFFFFF",
                                     textvariable=self.status_label_var)
        self.status_label.place(anchor="w", x=640, y=50, width=100, height=15)

        # Keep Button
        if self.s_id in self.root.control_window.configured_streams.keys():
            bg_color = "#00FF00"
        else:
            bg_color = "#FF0000"
        self.keep_button = tk.Button(self.frame, font=self.font, text="Keep", bg=bg_color,
                                     command=lambda: self.toggle_keep())
        self.keep_button.place(anchor="w", x=700, y=10, width=40, height=20)

        # Active Button
        self.active_button = tk.Button(self.frame, font=self.font, text="Active", bg=bg_color,
                                       command=lambda: self.toggle_active())
        self.active_button.place(anchor="w", x=700, y=30, width=40, height=20)

        self.update_thread = Thread(name=f"view_{s_id}_thread", target=self.update_view, daemon=True)
        self.update_thread.start()

    def set_input_device(self, _event):
        list_index = self.input_box.current()
        if self.s_id not in self.root.control_window.configured_streams:
            self.root.control_window.configured_streams[self.s_id] = self.create_s_id_info(self.s_id)
        elif self.root.control_window.configured_streams[self.s_id]["input_list_index"] == list_index:
            print("this input already running")
            return
        dev_index = self.root.control_window.c_dev_list[list_index][2]
        c_out = pyaudio.PyAudio()
        c_out = c_out.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=44100,
            input=True,
            output=False,
            frames_per_buffer=2048,
            input_device_index=dev_index
            # output_device_index=dev_index
         )
        info = self.root.control_window.configured_streams[self.s_id]
        info["input_list_index"] = list_index
        info["input_source"] = c_out
        info["input_buffer"] = []
        dev_name = f"{self.root.control_window.c_dev_list[list_index][0]} " \
                   f"{self.root.control_window.c_dev_list[list_index][1]}"
        info["input_name"] = dev_name
        print(f"SID {self.s_id} Input Device - {dev_name}")
        capture_thread = Thread(name="capture_thread_"+str(self.s_id), target=self.capture_thread_func,
                                     args=[self.s_id, list_index, c_out], daemon=True)
        capture_thread.start()

    def capture_thread_func(self, s_id, list_index, source):
        stream = self.root.control_window.configured_streams[s_id]
        while list_index == stream["input_list_index"]:
            new_frame = source.read(2048)
            f = np.frombuffer(new_frame, dtype=np.int16)
            self.vu_level_raw = max(f)
            # print("lvl:", self.vu_level, "raw_lvl:", self.vu_level_raw)
            stream["input_buffer"].append(new_frame)
            if stream["preview"] is False and len(stream["input_buffer"]) > 50:
                stream["input_buffer"] = stream["input_buffer"][-50:]
        print("capture thread ending")

    def preview_button_func(self, s_id):
        if self.root.control_window.sid_to_preview == s_id:
            self.root.control_window.sid_to_preview = -1
            self.root.control_window.status_label_var.set("Preview off")
            self.root.control_window.configured_streams[self.s_id]["preview"] = False
        else:
            self.root.control_window.sid_to_preview = s_id
            self.root.control_window.status_label_var.set(f"Preview ID {self.s_id}")
            self.root.control_window.configured_streams[self.s_id]["preview"] = True

    def output_config_button_func(self, s_id):
        _config_window = ConfigWindow(self.root, s_id)

    def toggle_keep(self):
        streams = self.root.control_window.configured_streams
        if self.s_id not in streams.keys():
            streams[self.s_id] = self.create_s_id_info(self.s_id)
        if streams[self.s_id]["keep"] is False:
            streams[self.s_id]["keep"] = True
            self.keep_button.configure(bg="#00FF00")
        else:
            streams[self.s_id]["keep"] = False
            self.keep_button.configure(bg="#FF0000")

    @staticmethod
    def create_s_id_info(s_id):
        print("creating new s_id", s_id)
        return {"input_name": None, "input_list_index": None, "input_source": None, "input_buffer": None,
                "output_name": None, "output_list_index": None, "output_source": None, "output_buffer": None,
                "output_type": "hardware", "host": "", "port": "", "mount": "", "password": "",
                "keep": False, "active": False, "status": "", "preview": False}

    def toggle_active(self):
        streams = self.root.control_window.configured_streams
        if self.s_id not in streams.keys():
            return
        info = streams[self.s_id]
        if info["active"] is True:
            self.active_button.configure(bg="#FF0000")
            self.status_label_var.set("Powering Down...")
            info["active"] = False
        else:
            self.active_button.configure(bg="#FFFF00")
            self.status_label_var.set("Powering Up...")
            info["active"] = True

    def get_volume_image(self, reset=False):
        v_size = 25
        size_x = 10
        size_y = 60
        new_image = np.zeros((v_size, 2, 3), dtype=np.int8)
        if not reset:
            self.vu_level = int((self.vu_level_raw / 32767) * v_size)
            self.vu_level = min(self.vu_level, v_size - 1)
            for v in range(v_size - self.vu_level, v_size):
                new_image[v, :, 1] = 255
        vol_image = Image.fromarray(new_image, "RGB").resize((size_x, size_y))
        return ImageTk.PhotoImage(vol_image)

    def update_view(self):
        while True:
            time.sleep(self.root.update_delay)
            self.output_label_var.set("icecast 192.168.5.121")
            self.volume_image = self.get_volume_image()
            self.volume_image_display.configure(image=self.volume_image)


class ConfigWindow:
    def __init__(self, root, s_id):
        self.width = 500
        self.height = 500
        self.root = root
        self.font = ("helvetica", 10)
        self.s_id = s_id
        self.output_type = 0
        self.elements = []
        self.frame = tk.Frame(self.root, width=self.width, height=self.height, bd=10, relief="ridge")
        self.frame.place(anchor="center", relx=0.5, rely=0.5)
        self.output_type_var = tk.IntVar()
        self.output_type_var.set(0)
        hw_radio_button = tk.Radiobutton(self.frame, text="hardware",
                                         variable=self.output_type_var, value=0, command=self.set_output_type)
        hw_radio_button.place(x=30, y=10)
        ice_radio_button = tk.Radiobutton(self.frame, text="icecast",
                                          variable=self.output_type_var, value=1, command=self.set_output_type)
        ice_radio_button.place(x=190, y=10)
        shout_radio_button = tk.Radiobutton(self.frame, text="shoutcast",
                                            variable=self.output_type_var, value=2, command=self.set_output_type)
        shout_radio_button.place(x=350, y=10)

        ok_button = tk.Button(self.frame, text="Ok", command=self.ok_func)
        ok_button.place(x=140, y=460, width=50, height=20)

        cancel_button = tk.Button(self.frame, text="Cancel", command=self.cancel_func)
        cancel_button.place(x=310, y=460, width=50, height=20)

        self.prepare_config_hardware()

    def set_output_type(self):
        if self.output_type == self.output_type_var.get():
            return
        self.output_type = self.output_type_var.get()
        print("output type", self.output_type)
        if self.output_type == 0:
            self.prepare_config_hardware()
        elif self.output_type == 1:
            self.prepare_config_icecast()
        elif self.output_type == 2:
            self.prepare_config_shoutcast()

    def clear_elements(self):
        for e in self.elements:
            e.destroy()

    def ok_func(self):
        if self.output_type == 0:
            output_box = self.elements[0]
            list_index = output_box.current()
            if self.s_id not in self.root.control_window.configured_streams:
                self.root.control_window.configured_streams[self.s_id] = StreamerWindow.create_s_id_info(self.s_id)
            elif self.root.control_window.configured_streams[self.s_id]["output_list_index"] == list_index:
                print("this output already running")
                return
            dev_index = self.root.control_window.p_dev_list[list_index][2]
            p_out = pyaudio.PyAudio()
            p_out = p_out.open(
                format=pyaudio.paInt16,
                channels=2,
                rate=44100,
                input=False,
                output=True,
                frames_per_buffer=2048,
                # input_device_index=dev_index
                output_device_index=dev_index
            )
            info = self.root.control_window.configured_streams[self.s_id]
            info["output_list_index"] = list_index
            info["output_source"] = p_out
            info["output_buffer"] = []
            dev_name = f"{self.root.control_window.p_dev_list[list_index][0]} " \
                       f"{self.root.control_window.p_dev_list[list_index][1]}"
            info["output_name"] = dev_name
            for w in self.root.stream_windows:
                if w.s_id == self.s_id:
                    w.output_label_var.set(dev_name)
                    break
            print(f"SID {self.s_id} Output Device - {dev_name}")
            playback_thread = Thread(name="playback_thread_" + str(self.s_id), target=self.playback_thread_func,
                                     args=[self.s_id, list_index, p_out], daemon=True)
            playback_thread.start()
        elif self.output_type == 1:
            pass
        elif self.output_type == 2:
            pass
        self.frame.destroy()

    def cancel_func(self):
        self.frame.destroy()

    def prepare_config_hardware(self):
        self.clear_elements()
        name_list = []
        for dev in self.root.control_window.p_dev_list:
            new_name = str(dev[0]) + ": " + str(dev[1])
            name_list.append(new_name)
        output_box = ttk.Combobox(self.frame, values=name_list, state="readonly", font=self.font)
        output_box.place(anchor="center", relx=0.5, rely=0.2, width=400, height=20)
        output_box.bind("<<ComboboxSelected>>", self.set_device_output)
        self.elements.append(output_box)

    def set_device_output(self, _event):
        pass

    def playback_thread_func(self, s_id, list_index, sink):
        stream = self.root.control_window.configured_streams[s_id]
        while list_index == stream["output_list_index"]:
            if len(stream["output_buffer"]) <= 5:
                sink.write(bytes(2048))
            else:
                sink.write(stream["output_buffer"].pop())
        print("playback thread ending")

    def prepare_config_icecast(self):
        self.clear_elements()

    def prepare_config_shoutcast(self):
        self.clear_elements()


app = MainWindow()
app.mainloop()
