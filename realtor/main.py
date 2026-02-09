import os
import time
import urllib
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple
import traceback

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd
import requests
from geopy.distance import distance as geo_distance
from homeharvest import scrape_property


# Ensure the environment variable are set
if "HOUSE_WEBHOOK" not in os.environ:
    raise ValueError("Environment variable 'HOUSE_WEBHOOK' is not set. Please set it to your Discord webhook URL.")
if "CENTRAL_COORD" not in os.environ:
    raise ValueError(
        "Environment variable 'CENTRAL_COORD' is not set. Please set it to your central coordinates e.g., 40.7128,-74.0060."
    )


def parse_coord(s: str) -> tuple[float, float]:
    lat_s, lon_s = [x.strip() for x in s.split(",")]
    return (float(lat_s), float(lon_s))


CENTRAL_COORD: tuple[float, float] = parse_coord(os.environ["CENTRAL_COORD"])
WEBHOOK = os.environ["HOUSE_WEBHOOK"]


PRICE_MAX = 350000
MAX_DISTANCE_MILES = 30  # Max distance from central point in miles
PAST_DAYS = 7  # Number of days to look back for listings
BUILD_CSV = True  # Set to True if you want to build a CSV file of the listings


DEBUG = False
MARKDOWN_OUTPUT = True
DISCORD_PUSH = True  # Set to False if you don't want to send messages to Discord
CHUNK_SIZE = 4  # Number of listings per Discord message chunk


@dataclass
class Criteria:
    location: str
    past_days: int
    price_max: int
    max_distance_miles: float
    central_coord: Tuple[float, float]
    require_min_bathrooms: float
    require_hoa_zero: bool = True
    ignore_pending: bool = True


def filter_properties(properties_df: pd.DataFrame, criteria: Criteria):
    """Filter properties based on specific criteria."""

    if "distance_miles" not in properties_df.columns:
        properties_df["distance_miles"] = 0.0

    # Identify and store dropped entries (those with missing lat/lon)
    dropped_properties = properties_df[properties_df[["latitude", "longitude"]].isna().any(axis=1)]
    if not dropped_properties.empty:
        properties_df = properties_df.dropna(subset=["latitude", "longitude"]).copy()

    # Calculate distances for each property and add to DataFrame
    coords = list(zip(properties_df["latitude"].astype(float), properties_df["longitude"].astype(float)))
    properties_df["distance_miles"] = [get_coords_distance(criteria.central_coord, coord) for coord in coords]

    mask = build_filter_mask(properties_df, criteria)
    dropped_mask = build_filter_mask(dropped_properties, criteria)

    return properties_df[mask], dropped_properties[dropped_mask]


def build_filter_mask(properties_df: pd.DataFrame, criteria: Criteria) -> pd.Series:
    """Build boolean mask for combined filter criterion."""
    masks = {}

    if "list_price" in properties_df.columns:
        price = pd.to_numeric(properties_df["list_price"], errors="coerce").fillna(0)
        masks["formatted_price"] = price <= criteria.price_max
    else:
        masks["formatted_price"] = pd.Series(True, index=properties_df.index)

    if "distance_miles" in properties_df.columns:
        distance = pd.to_numeric(properties_df["distance_miles"], errors="coerce").fillna(0)
        masks["distance"] = distance <= criteria.max_distance_miles
    else:
        masks["distance"] = pd.Series(True, index=properties_df.index)

    if criteria.require_hoa_zero and "hoa_fee" in properties_df.columns:
        hoa = pd.to_numeric(properties_df["hoa_fee"], errors="coerce").fillna(0)
        masks["hoa"] = hoa == 0
    else:
        masks["hoa"] = pd.Series(True, index=properties_df.index)

    if criteria.require_min_bathrooms:
        idx = properties_df.index
        full_raw = properties_df["full_baths"] if "full_baths" in properties_df.columns else pd.Series(0, index=idx)
        half_raw = properties_df["half_baths"] if "half_baths" in properties_df.columns else pd.Series(0, index=idx)

        full_baths = pd.to_numeric(full_raw, errors="coerce").fillna(0)
        half_baths = pd.to_numeric(half_raw, errors="coerce").fillna(0)

        bathrooms = full_baths + 0.5 * half_baths
        masks["bathrooms"] = bathrooms >= criteria.require_min_bathrooms
    else:
        masks["bathrooms"] = pd.Series(True, index=properties_df.index)

    combined_mask = pd.Series(True, index=properties_df.index)
    for mask in masks.values():
        combined_mask &= mask

    return combined_mask


def sort_properties(properties_df: pd.DataFrame):
    """Sort DataFrame in place based on specific criteria."""

    # properties_df = properties_df.sort_values("distance_miles")
    # properties_df = properties_df.sort_values("list_price", ascending=True)

    # sort by list date
    if "list_date" in properties_df.columns:
        properties_df = properties_df.sort_values("list_date", ascending=False)
    return properties_df


def send_to_discord(content: str, webhook: str = WEBHOOK) -> int:
    if DEBUG:
        print(f"Sending to Discord: {content}")
    if not DISCORD_PUSH:
        return 200
    data = {"content": content}
    response = requests.post(webhook, json=data, timeout=10)
    if DEBUG and not response.ok:
        print(response.status_code, response.text[:2000])
    time.sleep(0.5)
    return response.status_code


def build_google_maps_url(latitude, longitude) -> str:
    """Build a Google Maps URL for the given latitude and longitude."""
    return f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"


def build_google_maps_url_from_address(address):
    """Build a Google Maps URL for the given street address (non-API URL)."""
    base_url = "https://www.google.com/maps/search/"
    return base_url + urllib.parse.quote(address)


def fill_address_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Sterilize address related fields."""
    df = df.copy()
    df["street"] = df.get("street", "").fillna("Address Unavailable")
    df["city"] = df.get("city", "").fillna("")
    df["state"] = df.get("state", "").fillna("")
    if "zip_code" not in df.columns:
        df["zip_code"] = ""
    df["zip_code"] = df["zip_code"].fillna("").astype(str)
    return df


def format_listings(df: pd.DataFrame, max_paddings: dict[str, int]) -> str:
    """Format a given properties DataFrame into a Markdown string for Discord display."""

    # df = compute_fields_for_display(properties_df)

    lines = []
    for _, row in df.iterrows():
        # fmt: off
        line = (
            f"[🔗](<{row['property_url']}>) [:map:](<{build_google_maps_url_from_address(row['address'])}>) `"
            #f"[🔗](<{row['property_url']}>) [:map:](<{build_google_maps_url_from_address(row['address'])}>) [:frame_photo:](<{row['primary_photo']}>) `"
            + row["address"].ljust(max_paddings["address"]) + " | "
            + row["formatted_price"].ljust(max_paddings["formatted_price"]) + " | "
            + f"🛏 {row['beds'].ljust(max_paddings['beds'])} | "
            + f"🛁 {row['baths'].ljust(max_paddings['baths'])} | "
            + row["sqft"].ljust(max_paddings["sqft"]) + " | "
            + "Built: " + row["year_built"].ljust(max_paddings["year_built"]) + " | "
            + row["style"].ljust(max_paddings["style"]) + " | "
            + "Lot: " + row["lot"].ljust(max_paddings["lot"]) + " | "
            + "🅿️  " + row["parking"].ljust(max_paddings["parking"]) + " | "
            + "Distance: " + row["distance_miles"].ljust(max_paddings["distance_miles"]) + 'mi`'
        )
        # fmt: on
        lines.append(f"{line}")

    return f".\n{'\n'.join(lines)}\n"


def compute_fields_for_display(properties_df: pd.DataFrame) -> pd.DataFrame:
    """
    Helper function to preprocess and format raw field values for display in Discord.
    In some cases, new columns are added based on existing data e.g., combining full and half baths into a new column "baths".

    :param properties_df: The raw dataframe returned by HomeScraper.
    :type properties_df: pd.DataFrame
    :return: Description
    :rtype: pd.DataFrame
    """
    df = properties_df.copy()

    if "distance_miles" in df.columns:
        df["distance_miles"] = (
            pd.to_numeric(df["distance_miles"], errors="coerce").fillna(0).astype(float).round(1).astype(str)
        )
    else:
        df["distance_miles"] = "N/A"

    df = fill_address_fields(df)

    # Quick pass to infer types in place and ensure consistent formatting
    df = df.infer_objects(copy=False)

    df["address"] = df["street"] + ", " + df["city"] + ", " + df["state"] + " " + df["zip_code"].astype(str)
    df["formatted_price"] = "$" + pd.to_numeric(df["list_price"], errors="coerce").fillna(0).astype(int).map(
        lambda x: f"{x:,}"
    )
    df["beds"] = pd.to_numeric(df["beds"], errors="coerce").fillna(0).astype(int).astype(str)
    full_baths = pd.to_numeric(df.get("full_baths"), errors="coerce").fillna(0).astype(int)
    half_baths = pd.to_numeric(df.get("half_baths"), errors="coerce").fillna(0).astype(int)
    df["baths"] = (full_baths + 0.5 * half_baths).astype(str)
    df["sqft"] = pd.to_numeric(df["sqft"], errors="coerce").fillna(0).astype(int).astype(str) + " sqft"
    df["year_built"] = pd.to_numeric(df["year_built"], errors="coerce").fillna(0).astype(int).astype(str)
    df["style"] = df["style"].fillna("")
    df["lot"] = pd.to_numeric(df.get("lot_sqft"), errors="coerce").fillna(0).astype(int).astype(str) + " sqft"
    df["parking"] = df["parking_garage"].fillna("—").astype(str)
    df["property_url"] = df["property_url"].fillna("#")

    return df


def get_max_padding(df: pd.DataFrame) -> dict[str, int]:
    """
    Get the maximum padding required for each column in the DataFrame and return as a dictionary.
    """

    # df = compute_fields_for_display(df)

    col_widths = {
        "address": df["address"].map(len).max() + 10,
        "formatted_price": df["formatted_price"].map(len).max() + 1,
        "beds": df["beds"].map(len).max(),
        "baths": df["baths"].map(len).max() + 1,
        "sqft": df["sqft"].map(len).max() + 1,
        "year_built": df["year_built"].map(len).max(),
        "style": df["style"].map(len).max(),
        "lot": df["lot"].map(len).max() + 1,
        "parking": df["parking"].map(len).max(),
        "distance_miles": df["distance_miles"].map(len).max() + 1,
    }

    return col_widths


def get_row_distance(row):
    prop_coord = (row["latitude"], row["longitude"])
    return get_coords_distance(CENTRAL_COORD, prop_coord)


def get_coords_distance(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """
    Calculate the distance between two coordinates using geopy.
    :param coord1: Tuple of (latitude, longitude) for the first coordinate.
    :param coord2: Tuple of (latitude, longitude) for the second coordinate.
    :return: Distance in miles.
    """
    return round(geo_distance(coord1, coord2).miles, 1)


def chunk_dataframe(df, chunk_size=CHUNK_SIZE, chunk_limit=None):
    """Yield successive chunk_size-sized chunks from a DataFrame."""
    if chunk_limit is None:
        chunk_limit = len(df)
    for i in range(0, chunk_limit, chunk_size):
        yield df.iloc[i : i + chunk_size]


def build_listings_header(total, matched, max_price, max_distance):
    # top =    "╔" + "═" + "╗"
    # title =  "║ BEGIN LISTINGS REPORT" + "║"
    # middle = "╠" + "═" + "╣"
    # line1 =  f"║ Total listings searched: {total}" + "║"
    # line2 =  f"║ Matching filters:        {matched}" + "║"
    # bottom = "╚" + "╝"
    # message_list = [top, title, middle, line1, line2, bottom]

    spacing_adjust = 51  # len(max(message_list, key=len))

    top = "╔" + "═" * spacing_adjust + "╗"
    title = "║ BEGIN LISTINGS REPORT".ljust(spacing_adjust + 1) + "║"
    middle = "╠" + "═" * spacing_adjust + "╣"
    line1 = f"║ Total listings searched: {total}".ljust(spacing_adjust + 1) + "║"
    line2 = f"║ Matching filters:        {matched}".ljust(spacing_adjust + 1) + "║"
    bottom = "╚" + "═" * spacing_adjust + "╝"

    return ".`\n" + "\n".join([top, title, middle, line1, line2, bottom]) + "`"


# ----------------------------
# Tkinter UI
# ----------------------------


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HomeHarvest UI")
        self.geometry("980x720")

        self.q: queue.Queue = queue.Queue()
        self.worker: Optional[threading.Thread] = None

        # Defaults
        env_coord = os.environ.get("CENTRAL_COORD", "42.10,-72.60")
        env_webhook = os.environ.get("HOUSE_WEBHOOK", "")

        self.var_location = tk.StringVar(value="Massachusetts")
        self.var_past_days = tk.IntVar(value=7)
        self.var_price_max = tk.IntVar(value=350000)
        self.var_distance = tk.DoubleVar(value=30.0)
        self.var_coord = tk.StringVar(value=env_coord)
        self.var_hoa_zero = tk.BooleanVar(value=True)
        self.var_ignore_pending = tk.BooleanVar(value=True)
        self.var_min_bathrooms = tk.DoubleVar(value=0.0)

        self.var_discord = tk.BooleanVar(value=bool(env_webhook))
        self.var_webhook = tk.StringVar(value=env_webhook)

        self.var_save_csv = tk.BooleanVar(value=False)

        self._build_ui()
        self.after(100, self._poll_queue)

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        # Inputs
        inputs = ttk.LabelFrame(frm, text="Criteria", padding=12)
        inputs.pack(fill="x")

        def row(label, widget, r):
            ttk.Label(inputs, text=label).grid(row=r, column=0, sticky="w", padx=(0, 10), pady=4)
            widget.grid(row=r, column=1, sticky="ew", pady=4)
            inputs.grid_columnconfigure(1, weight=1)

        row("Location", ttk.Entry(inputs, textvariable=self.var_location), 0)
        row("Past days", ttk.Spinbox(inputs, from_=1, to=60, textvariable=self.var_past_days, width=8), 1)
        row(
            "Max price",
            ttk.Spinbox(inputs, from_=50000, to=10000000, increment=5000, textvariable=self.var_price_max, width=8),
            2,
        )
        row(
            "Max distance (miles)",
            ttk.Spinbox(inputs, from_=5, to=100, increment=5, textvariable=self.var_distance, width=8),
            3,
        )
        row("Central coord (lat,lon)", ttk.Entry(inputs, textvariable=self.var_coord), 4)
        row(
            "Min bathrooms",
            ttk.Spinbox(inputs, from_=0, to=5, increment=0.5, textvariable=self.var_min_bathrooms, width=8),
            5,
        )

        ttk.Checkbutton(inputs, text="Ignore Listings with HOAs", variable=self.var_hoa_zero).grid(
            row=6, column=1, sticky="w", pady=4
        )

        ttk.Checkbutton(inputs, text="Ignore Pending/Contingent Listings", variable=self.var_ignore_pending).grid(
            row=7, column=1, sticky="w", pady=4
        )

        # Discord
        discord = ttk.LabelFrame(frm, text="Discord", padding=12)
        discord.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(discord, text="Send to Discord", variable=self.var_discord).grid(row=0, column=0, sticky="w")
        ttk.Label(discord, text="Webhook URL").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(discord, textvariable=self.var_webhook).grid(row=2, column=0, sticky="ew")
        discord.grid_columnconfigure(0, weight=1)

        # Output options + buttons
        opts = ttk.Frame(frm)
        opts.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(opts, text="Save CSV", variable=self.var_save_csv).pack(side="left")
        ttk.Button(opts, text="Run scrape", command=self.on_run).pack(side="right")
        ttk.Button(opts, text="Stop (best-effort)", command=self.on_stop).pack(side="right", padx=(0, 8))

        # Status
        self.status = tk.StringVar(value="Idle.")
        ttk.Label(frm, textvariable=self.status).pack(anchor="w", pady=(10, 0))

        # Output box
        out = ttk.LabelFrame(frm, text="Results", padding=8)
        out.pack(fill="both", expand=True, pady=(10, 0))

        self.txt = tk.Text(out, wrap="word")
        self.txt.pack(fill="both", expand=True)
        self.txt.insert("end", "Ready.\n")

    def log(self, s: str):
        self.txt.insert("end", s + "\n")
        self.txt.see("end")

    def on_run(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Running", "A scrape is already running.")
            return

        try:
            coord = parse_coord(self.var_coord.get())
        except Exception:
            messagebox.showerror("Bad coord", "Central coord must look like: 40.7128,-74.0060")
            return

        if self.var_discord.get() and not self.var_webhook.get().strip():
            messagebox.showerror("Missing webhook", "Discord enabled but webhook URL is empty.")
            return

        c = Criteria(
            location=self.var_location.get().strip(),
            past_days=int(self.var_past_days.get()),
            price_max=int(self.var_price_max.get()),
            max_distance_miles=float(self.var_distance.get()),
            central_coord=coord,
            require_min_bathrooms=float(self.var_min_bathrooms.get()),
            require_hoa_zero=bool(self.var_hoa_zero.get()),
            ignore_pending=bool(self.var_ignore_pending.get()),
        )

        self._stop_flag = False
        self.status.set("Running scrape…")
        self.txt.delete("1.0", "end")
        self.log("Starting…")

        self.worker = threading.Thread(target=self._worker_run, args=(c,), daemon=True)
        self.worker.start()

    def on_stop(self):
        # best-effort: we can’t reliably abort a network call mid-flight, but we can stop after it returns
        self._stop_flag = True
        self.status.set("Stop requested (best-effort).")

    def _worker_run(self, c: Criteria):
        try:
            self.q.put(("log", f"Scraping location={c.location}, past_days={c.past_days}"))
            df = scrape_property(
                location=c.location, listing_type="for_sale", exclude_pending=c.ignore_pending, past_days=c.past_days
            )
            total_listings = len(df)
            self.q.put(("log", f"Scraped {total_listings} listings."))

            if self._stop_flag:
                self.q.put(("done", "Stopped."))
                return

            # Note: `dropped` here is the subset of the filtered df that was dropped due solely to missing lat/lon coords
            df, dropped = filter_properties(df, c)

            df = sort_properties(df)
            df = compute_fields_for_display(df)

            self.q.put(("log", f"Matched {len(df)} after filters."))

            if self.var_save_csv.get():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_name = f"HomeHarvest_{ts}.csv"
                self.q.put(("savecsv", (df, default_name)))

            if self.var_discord.get():
                webhook = self.var_webhook.get().strip()
                header = build_listings_header(
                    total=total_listings, matched=len(df), max_price=c.price_max, max_distance=c.max_distance_miles
                )

                full_message_string = header
                code = send_to_discord(header, webhook=webhook)
                self.q.put(("log", f"Discord header → HTTP {code}"))

                num_of_chunks = (len(df) + CHUNK_SIZE - 1) // CHUNK_SIZE

                max_paddings = get_max_padding(df)

                for i, chunk in enumerate(chunk_dataframe(df, chunk_size=CHUNK_SIZE, chunk_limit=None), 1):
                    message = format_listings(chunk, max_paddings)
                    full_message_string += message
                    code = send_to_discord(message, webhook=webhook)
                    self.q.put(("log", f"Discord chunk {i}/{num_of_chunks} → HTTP {code}"))

                if not dropped.empty:
                    dropped = sort_properties(dropped)
                    dropped = compute_fields_for_display(dropped)

                    total_dropped = len(dropped)

                    SPACING_ADJUST = 51
                    header = (
                        ".`\n"
                        "╔" + "═" * SPACING_ADJUST + "╗\n"
                        f"║ Dropped {total_dropped} properties due to missing coordinates:".ljust(SPACING_ADJUST + 3)
                        + "║"
                        "\n╚" + "═" * SPACING_ADJUST + "╝`"
                    )
                    code = send_to_discord(header, webhook=webhook)
                    self.q.put(("log", f"Discord dropped listings header → HTTP {code}"))

                    full_message_string += header

                    num_of_chunks = (total_dropped + CHUNK_SIZE - 1) // CHUNK_SIZE

                    for i, chunk in enumerate(chunk_dataframe(dropped, chunk_size=CHUNK_SIZE, chunk_limit=None), 1):
                        message = format_listings(chunk, max_paddings)
                        full_message_string += message
                        code = send_to_discord(message, webhook=webhook)
                        self.q.put(("log", f"Discord dropped chunk {i}/{num_of_chunks} → HTTP {code}"))

            self.q.put(("done", "Done."))

        except Exception as e:
            self.q.put(("error", traceback.format_exc()))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.log(payload)
                elif kind == "settext":
                    self.txt.delete("1.0", "end")
                    self.txt.insert("end", payload)
                elif kind == "savecsv":
                    df, default_name = payload
                    path = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        initialfile=default_name,
                        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    )
                    if path:
                        df.to_csv(path, index=False)
                        self.log(f"Saved CSV: {path}")
                elif kind == "done":
                    self.status.set(payload)
                    self.log(payload)
                elif kind == "error":
                    self.status.set("Error.")
                    self.txt.insert("end", "\n\n" + payload + "\n")
                    self.txt.see("end")
                    messagebox.showerror("Error", payload.splitlines()[-1])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)


if __name__ == "__main__":
    App().mainloop()
