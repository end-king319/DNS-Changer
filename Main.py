import customtkinter as ctk
import subprocess
import os
import webbrowser
import json
import warnings
import pyuac
import ctypes
import sys


from dns_providers import DNS_PROVIDERS
from network_adapters import get_all_nic_details, detect_default_network_interface
from updater import check_Update
from version import VERSION
from PIL import Image, ImageTk


ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

warnings.filterwarnings("ignore", message=".*is not CTkImage.*")


# Initial settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


app_bg_color = "#080d10"

btns_text_color = "#ecf0f3"
btns_fg = "#25a2a4"
btns_bg = "transparent"
btns_ho = "#10516bff"
btns_ac = "#50c16f"
btns_ac_ho = "#10516bff"
btn_cls_ac = "#eff404"

labels_bg = "#080d10"
labels_fg = "#ecf0f3"


# Config file
config_path = "config.json"
CONFIG_FILE = "config.json"
target_nic_name = None
custom_dnss = {}
all_providers = {"":["", ""]}
c : dict = {}

# Load JSON data from a file
def load_config(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        # If the file doesn't exist, return a default structure
        return {"target_nic_name": "", "custom_dnss": {}}

# Save JSON data to a file
def save_config(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

# Add a named DNS entry
def add_dns(file_path, name, primary_ip, secondary_ip):
    config = load_config(file_path)
    if "custom_dnss" in config and isinstance(config["custom_dnss"], dict):
        config["custom_dnss"][name] = [primary_ip, secondary_ip]
        print(f"Added or updated DNS entry: {name} -> [{primary_ip}, {secondary_ip}]")
    else:
        print("Invalid structure for 'custom_dnss'. Resetting...")
        config["custom_dnss"] = {name: [primary_ip, secondary_ip]}
    save_config(file_path, config)
    app.refresh_custom_dns_buttons()

# Remove a named DNS entry
def remove_dns(file_path, name):
    config = load_config(file_path)
    if "custom_dnss" in config and isinstance(config["custom_dnss"], dict):
        if name in config["custom_dnss"]:
            del config["custom_dnss"][name]
            save_config(file_path, config)
            print(f"Removed DNS entry: {name}")
        else:
            print(f"DNS entry '{name}' not found.")
    else:
        print("Invalid structure for 'custom_dnss'.")
    app.refresh_custom_dns_buttons()

# Function to set DNS
def set_DNS(nic_name, provider):
    primary_dns = provider[0]
    secondary_dns = provider[1]
    os.system(f'netsh interface ip set dns name="{nic_name}" static {primary_dns}')
    os.system(f'netsh interface ip add dns name="{nic_name}" {secondary_dns} index=2')
    os.system("ipconfig /flushdns")

# Function to clear DNS
def clear_DNS(nic_name):
    os.system(f'netsh interface ipv4 delete dns "{nic_name}" all')
    os.system("ipconfig /flushdns")

# Function to flush DNS
def flush_dns():
    os.system("ipconfig /flushdns")

# Function to get DNS status
def get_dns_status(nic_name):
    nics = get_all_nic_details()

    for nic in nics:
        if nic["name"] != nic_name:
            continue

        if (
            nic["dhcp_server"]
            and len(nic["dns_servers"]) == 1
            and nic["dns_servers"][0] == nic["dhcp_server"]
        ):
            return "DNS Server Not set"  # If DNS is not set, return this message


        if len(nic["dns_servers"]) > 1:
            print(type(nic["dns_servers"]))
            for provider, servers in all_providers.items():
                print(f"{provider} -> {servers} -> Types: {type(servers)}")
            print(f"Looking for DNS servers: {nic['dns_servers']}")
            print(all_providers)
            for provider, servers in all_providers.items():
                print(f"Checking {provider}: {servers}")
                if list(servers) == nic["dns_servers"]:
                    print(f"Match found: {provider}")
                    return provider  # Return the exact match for the DNS provider
        print("No match found.")
        return None  # Return None if no match is found       

        return get_current_dns()

    return "Oops!!! No DNS found"

def get_current_dns():
    """Get all current DNS settings"""
    try:
        # Run ipconfig command and capture output
        result = subprocess.run(['ipconfig', '/all'], capture_output=True, text=True)
        dns_servers = []
        capture_dns = False

        # Parse the output line by line
        for line in result.stdout.splitlines():
            line = line.strip()  # Remove leading/trailing whitespace
            # Start capturing when "DNS Servers" is found
            if "DNS Servers" in line:
                capture_dns = True
                # Extract the first DNS server
                dns = line.split(":", 1)[1].strip()
                dns_servers.append(dns)
            elif capture_dns and line:  # Check for non-empty subsequent indented lines
                if line[0].isdigit():  # Ensure the line starts with a number (valid IP)
                    dns_servers.append(line)
            else:
                capture_dns = False  # Stop capturing on unrelated lines

        return dns_servers
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def add_dns_action(name, dns_list):
    messagebox.showinfo("DNS Selected", f"Name: {name}\nPrimary: {dns_list[0]}\nSecondary: {dns_list[1]}")


# Building the GUI
class DNSChangerApp(ctk.CTk):
    def __init__(self):
       # Check admin rights
        if not ctypes.windll.shell32.IsUserAnAdmin():
            pyuac.runAsAdmin()  # This launches a new admin instance
            sys.exit(0)  # Close the non-admin instance gracefully
        super().__init__()


        self.title("DNS Changer")
        self.geometry("400x800")

        # Load config once at the start
        self.config = load_config(config_path)
        self.custom_dns = self.config.get("custom_dnss", {})
        # Use a proper default (None or "") if target_nic_name is missing
        initial_nic_name = self.config.get("target_nic_name", None)

        global all_providers
        # Ensure custom_dns is used here, not dns_providers which is a copy
        all_providers = DNS_PROVIDERS | self.custom_dns

        print(all_providers)
        self.resizable(False, False)

        # Set nic_name based on loaded config or detection
        self.nic_name = initial_nic_name or detect_default_network_interface()
        # Update the config dictionary if a default was detected and none was saved
        if not initial_nic_name and self.nic_name:
             self.config["target_nic_name"] = self.nic_name
             # Optionally save immediately or wait for user action
             # save_config(config_path, self.config)

        self.background_label = ctk.CTkLabel(self, bg_color=app_bg_color)
        self.background_label.place(relwidth=1, relheight=1)
        # Program title
        self.label = ctk.CTkLabel(self, text="DNS Changer", font=("Montserrat-Bold", 30), bg_color=labels_bg, text_color=labels_fg)
        self.label.pack(pady=25)

        # Display selected network adapter in label
        # Ensure nic_name is a string for the label
        nic_display_name = self.nic_name if self.nic_name else "None Selected"
        self.nic_label = ctk.CTkLabel(self, text=f"Selected Adapter: {nic_display_name}", font=("Montserrat-Regular",14),bg_color= labels_bg, text_color=labels_fg)
        self.nic_label.pack(pady=0)

        # Create DNS buttons instead of dropdown menu
        self.dns_buttons_frame = ctk.CTkFrame(self)
        self.dns_buttons_frame.pack(pady=10)

        self.dns_buttons = {}  # Store the buttons for later reference
        row, col = 0, 0  # Start from the first row and column

        for index, provider_name in enumerate(DNS_PROVIDERS):
            dns_button = ctk.CTkButton(
                self.dns_buttons_frame,
                text=provider_name,
                command=lambda p=provider_name: self.set_dns(p),
                width=150,  # Set button width to align buttons better
            )
            dns_button.grid(row=row, column=col, padx=5, pady=5)  # Place in grid layout
            self.dns_buttons[provider_name] = dns_button  # Save button for reference

            row += 1
        
        # Frame for custom DNS buttons
        self.custom_dnss_frame = ctk.CTkFrame(self)
        self.custom_dnss_frame.pack(pady=5)
        self.custom_dns_buttons = {}
        self.custom_dnss_frame.pack(pady=5)
        self.custom_dns_buttons = {}
        
        
        self.refresh_custom_dns_buttons()
        # Button to add a custom DNS, placed below the DNS buttons
        self.add_custom_dns_button = ctk.CTkButton(self, text="Custom DNS", command=self.add_custom_dns, fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color)
        self.add_custom_dns_button.pack(pady=10)


        # Clear DNS button
        self.clear_dns_button = ctk.CTkButton(self, text="Clear DNS", command=self.clear_dns, fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color)
        self.clear_dns_button.pack(pady=5)


        # Flush DNS button
        self.flush_dns_button = ctk.CTkButton(self, text="Flush DNS", command=self.flush_dns, fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color)
        self.flush_dns_button.pack(pady=5)

        # Get DNS status button
        self.get_dns_status_button = ctk.CTkButton(self, text="Get DNS Status", command=self.show_current_dns, fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color)
        self.get_dns_status_button.pack(pady=5)

        # Select Adapter button to show/hide adapter selection dropdown
        self.select_adapter_button = ctk.CTkButton(self, text="Select Adapter", command=self.toggle_adapter_selector, fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color)
        self.select_adapter_button.pack(pady=5)

        # Adapter dropdown menu and Done button (initially None)
        self.adapter_menu = None
        self.done_button = None # Initialize done_button attribute

        # Check for updates button
        self.update_button = ctk.CTkButton(self, text="Check for Updates", command=self.check_update, fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color)
        self.update_button.pack(pady=5)

        # Open GitHub page button
        self.github_button = ctk.CTkButton(self, text="Github Page", command=self.open_github, fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color)
        self.github_button.pack(pady=5)

        # Quit button
        self.quit_button = ctk.CTkButton(self, text="Quit", command=self.quit_app, fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color)
        self.quit_button.pack(pady=5)

        # Status area
        self.status_label = ctk.CTkLabel(self, text="Status: Ready", font=("Arial", 12),bg_color= labels_bg, text_color=labels_fg)
        self.status_label.pack(pady=10)

        # Display program version
        self.version_label = ctk.CTkLabel(self, text=f"Version: {VERSION}", font=("Arial", 10),bg_color= labels_bg, text_color=labels_fg)
        self.version_label.pack(side="bottom", pady=0)

        self.version_label = ctk.CTkLabel(self, text="By Aedan Gaming", font=("Arial", 10),bg_color= labels_bg, text_color=labels_fg)
        self.version_label.pack(side="bottom", pady=5)


        # Update DNS status and button colors on start
        self.show_dns_status()

    # Function to create buttons dynamically
    def create_custom_dns_button(self):
        self.config = load_config(config_path)
        self.custom_dns = self.config.get("custom_dnss", {})
        for index, custom_dns_names in enumerate(self.custom_dns):
            self.frame = ctk.CTkFrame(self.custom_dnss_frame)
            self.frame.pack(pady=0)
            custom_dns_button = ctk.CTkButton(
                self.frame,
                text=custom_dns_names,
                fg_color=btns_fg,
                bg_color=btns_bg,
                hover_color=btns_ho,
                text_color=btns_text_color,
                command=lambda n=custom_dns_names: self.set_dns(n),
                width=150,
            )
            custom_dns_button.pack(pady=5,side="left")
            def make_remove_handler(n):
                return lambda: remove_dns(config_path,custom_dns_names)
        
            
            ctk.CTkButton(self.frame, text="Remove",fg_color=btns_fg,bg_color=btns_bg, 
                      command=make_remove_handler(custom_dns_names),width=50).pack(pady=5,padx=5,side="right")
            self.custom_dns_buttons[custom_dns_names] = custom_dns_button  # Save button for reference

    def refresh_custom_dns_buttons(self):
        self.config = load_config(config_path)
        self.custom_dns = self.config.get("custom_dnss", {})
        if self.custom_dnss_frame.winfo_children():
            for items in self.custom_dnss_frame.winfo_children():
                items.destroy()
            self.custom_dnss_frame.configure(width=1,height=0)
        else:
            self.custom_dnss_frame.configure(width=1,height=0)
        self.create_custom_dns_button()
        

    def show_current_dns(self):
        """Show current DNS settings"""
        # Fetch current DNS settings
        current_dns = get_current_dns()
        print(get_current_dns())
        
        # Prepare output
        if current_dns:
            dns_text = "\n".join(current_dns)
            messagebox.showinfo("Current DNS Settings", f"\n{dns_text}")
        else:
            messagebox.showinfo("Current DNS Settings", "Unable to retrieve current DNS settings.")
           
    # Function to set DNS for selected provider
    def set_dns(self, provider_name):
        if provider_name:
            # Detect default adapter if none is selected
            if not self.nic_name:
                self.nic_name = detect_default_network_interface()

            if self.nic_name:
                dns = DNS_PROVIDERS.get(provider_name, None) or self.dns_providers.get(provider_name, None)
                if dns:
                    set_DNS(self.nic_name, dns)
                    self.status_label.configure(
                        text=f"DNS set to {provider_name} for {self.nic_name}"
                    )
                else:
                    self.status_label.configure(text=f"{provider_name} not found in DNS providers.")
            else:
                self.status_label.configure(text="No active network adapter found.")

        self.show_dns_status()

    def clear_dns(self):
        if self.nic_name:
            clear_DNS(self.nic_name)
            self.status_label.configure(text="DNS cleared.")
            self.show_dns_status()

    def flush_dns(self):
        flush_dns()
        self.status_label.configure(text="DNS flushed.")
        self.show_dns_status()

    def toggle_adapter_selector(self):
        if not hasattr(self, "adapter_menu") or self.adapter_menu is None:
            adapter_names = [nic["name"] for nic in get_all_nic_details()]
            if not adapter_names:
                # Use messagebox from tkinter or customtkinter
                # Assuming you have imported it like: from tkinter import messagebox
                # Or adapt if using customtkinter's message box equivalent
                import tkinter.messagebox as messagebox
                messagebox.showerror("Error", "No network adapters found.")
                return

            self.adapter_menu = ctk.CTkComboBox(
                self,
                values=adapter_names,
                command=self.select_adapter # This updates self.nic_name immediately on selection
            )
            # Set the initial value of the combobox if an adapter is already selected
            if self.nic_name in adapter_names:
                self.adapter_menu.set(self.nic_name)

            # Create the Done button only once
            if not self.done_button:
                 self.done_button = ctk.CTkButton(
                    self, text="Done", fg_color=btns_fg, hover_color=btns_ho,
                    # *** Crucial Change: Command should be save_and_hide_adapter_menu ***
                    command=self.save_and_hide_adapter_menu
                )

        if self.adapter_menu.winfo_ismapped():
            # Hide widgets and shrink window
            self.adapter_menu.pack_forget()
            if self.done_button: # Check if done_button exists
                self.done_button.pack_forget()
            self.geometry("400x800")  # Restore to original size
        else:
            # Show widgets and expand window
            self.adapter_menu.pack(pady=5)
            if self.done_button: # Check if done_button exists
                self.done_button.pack(pady=5)
            self.geometry("400x900")  # Adjust to fit the widgets

    def select_adapter(self, adapter_name):
        self.nic_name = adapter_name

    def save_and_hide_adapter_menu(self):
        # This method is now correctly called by the Done button
        if self.nic_name:
            # Update the config dictionary stored in the instance
            self.config["target_nic_name"] = self.nic_name
            # Save the entire updated config dictionary
            save_config(config_path, self.config)
            # Update the label (might be redundant if select_adapter already did)
            self.nic_label.configure(text=f"Selected Adapter: {self.nic_name}")

        # Hide the controls and resize window
        if self.adapter_menu:
            self.adapter_menu.pack_forget()
        if self.done_button:
            self.done_button.pack_forget()
        self.geometry("400x800") # Restore original size

    def add_custom_dns(self):
        self.custom_dns_window = ctk.CTkToplevel(self)
        self.custom_dns_window.title("Add Custom DNS")
        self.custom_dns_window.geometry("300x350")
        self.custom_dns_window.resizable(False, False)
        # Set the background color directly on the Toplevel window
        self.custom_dns_window.configure(fg_color=app_bg_color)

        # Remove the background label as it's no longer needed
        # add_background_label = ctk.CTkLabel(self.custom_dns_window, text="", fg_color=app_bg_color)
        # add_background_label.place(relwidth=1, relheight=1)

        #name
        # Ensure labels don't have their own fg_color set
        dns_name_label = ctk.CTkLabel(self.custom_dns_window, text="DNS Name:", text_color=labels_fg, font=("Montserrat-Bold", 14))
        dns_name_label.pack(pady=10)
        self.dns_name_label_entry = ctk.CTkEntry(self.custom_dns_window)
        self.dns_name_label_entry.pack(pady=5)

        # Primary DNS input
        primary_label = ctk.CTkLabel(self.custom_dns_window, text="Primary DNS:", text_color=labels_fg, font=("Montserrat-Bold", 14))
        primary_label.pack(pady=10)
        self.primary_dns_entry = ctk.CTkEntry(self.custom_dns_window)
        self.primary_dns_entry.pack(pady=5)

        # Secondary DNS input
        secondary_label = ctk.CTkLabel(self.custom_dns_window, text="Secondary DNS:", text_color=labels_fg, font=("Montserrat-Bold", 14))
        secondary_label.pack(pady=10)
        self.secondary_dns_entry = ctk.CTkEntry(self.custom_dns_window)
        self.secondary_dns_entry.pack(pady=5)

        # Save button
        save_button = ctk.CTkButton(
            self.custom_dns_window,
            text="Save",
            fg_color=btns_fg,
            hover_color=btns_ho,
            text_color=btns_text_color,
            command=self.save_custom_dns
        )
        save_button.pack(pady=20)

    def save_custom_dns(self):
        dns_name = self.dns_name_label_entry.get()
        primary_dns = self.primary_dns_entry.get()
        secondary_dns = self.secondary_dns_entry.get()

        if primary_dns and secondary_dns:
            add_dns(config_path,str(dns_name), primary_dns, secondary_dns)
            self.custom_dns_window.destroy()


    def show_dns_status(self):
        current_dns = get_current_dns()
        if current_dns:
            dns_text = "\n".join(current_dns)
        if self.nic_name:
            dns_status = get_dns_status(self.nic_name)
            self.status_label.configure(text=f"\n{dns_text}")

            #print(self.custom_dns_buttons)
            #print(self.dns_buttons)
            self.all_dns_buttons = {}
            self.all_dns_buttons =  self.dns_buttons | self.custom_dns_buttons 
            #print(self.all_dns_buttons)
            # Update button colors based on DNS status
            for provider_name, button in self.dns_buttons.items():
                if dns_status == provider_name:
                    button.configure(fg_color=btns_ac,bg_color=btns_bg,hover_color=btns_ac_ho,text_color=btns_text_color)  # Change button color
                else:
                    button.configure(fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color) # Reset other buttons to blue


            for provider_name, button in self.custom_dns_buttons.items():
                if dns_status == provider_name:
                    button.configure(fg_color=btns_ac,bg_color=btns_bg,hover_color=btns_ac_ho,text_color=btns_text_color)  # Change button color
                else:
                    button.configure(fg_color=btns_fg,bg_color=btns_bg,hover_color=btns_ho,text_color=btns_text_color) # Reset other buttons to blue
            # Check if DNS is not set, and change the color of the "Clear DNS" button
            if dns_status == "DNS Server Not set" or dns_status == "Oops!!! No DNS found":
                self.clear_dns_button.configure(fg_color=btn_cls_ac)
            # Set Clear DNS button to green
            else:
                self.clear_dns_button.configure(fg_color=btns_fg,bg_color=btns_bg,text_color=btns_text_color)  # Reset Clear DNS button color

    def check_update(self):
        if check_Update():
            self.status_label.configure(text="New update available!")
        else:
            self.status_label.configure(text="No updates available.")


    def open_github(self):
        webbrowser.open("https://github.com/aedangaming/DNS-Changer")

    def quit_app(self):
        self.destroy()

# Run the program
if __name__ == "__main__":
    def handle_exception(exc_type, exc_value, exc_traceback):
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        with open("error.log", "a") as f:
            f.write(f"Crash Report:\n{error_msg}\n")
        sys.exit(1)

    sys.excepthook = handle_exception
    app = DNSChangerApp()
    app.mainloop()