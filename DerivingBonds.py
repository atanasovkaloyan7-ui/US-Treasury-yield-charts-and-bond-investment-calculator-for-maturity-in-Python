import pandas as pd
import yfinance as yf
import tkinter as tk
from tkinter import messagebox
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter, PercentFormatter

#Importing Yields
TICKERS = {"US03M": "^IRX", "US05Y": "^FVX","US10Y": "^TNX"}
HISTORY_YEARS = 10                                     # how many years of history to chart

#Data
data = yf.download(list(TICKERS.values()), period=f"{HISTORY_YEARS}y", progress=False)["Close"]
data = data.rename(columns={ticker: name for name, ticker in TICKERS.items()})
data = data[["US03M", "US05Y", "US10Y"]]
data = data.dropna()
if data.empty:
    raise SystemExit("Could not download yields from Yahoo. Check your internet and try again.")

#Price function
def bond_price(yield_pct, coupon_pct, years, face=100):
    y = yield_pct / 100 / 2           # yield per half-year
    c = coupon_pct / 100 / 2 * face   # coupon paid every half-year
    periods = int(years * 2)          # number of coupon payments

    price = 0
    for t in range(1, periods + 1):
        price += c / (1 + y) ** t                # today's value of each coupon
    price += face / (1 + y) ** (years * 2)       # today's value of the $100 at the end
    return price

#print(round(bond_price(4, 4, 10), 2))   # coupon = yield
#print(round(bond_price(5, 4, 10), 2))   # yield above coupon
#print(round(bond_price(3, 4, 10), 2))   # yield below coupon

MATURITY_YEARS = {"US03M": 0.25, "US05Y": 5, "US10Y": 10}
prices = pd.DataFrame(index=data.index)
for name, years in MATURITY_YEARS.items():
    coupon = data[name].iloc[0]
    prices[name] = bond_price(data[name], coupon, years)

#Investment calculator
def duration_text(years):
    return f"{round(years * 12)} months" if years < 1 else f"{years} years"

def calculate(amount, bond):
    y = data[bond].iloc[-1]                              # today's yield (last row)
    years = MATURITY_YEARS[bond]                         # how long the bond lasts

    coupon = 0 if years < 1 else y                       # T-bills pay no coupon
    price = bond_price(y, coupon, years)                 # price per $100 of face value
    face = amount / price * 100                          # how much face value your money buys
    each_coupon = face * coupon / 100 / 2                # one coupon payment (every 6 months)
    n_coupons = int(years * 2)                           # how many coupon payments you get
    final = face + each_coupon * n_coupons
    interest = final - amount

    #Your money over time: a coupon every 6 months, the face value back at the end
    if coupon == 0:
        #T-bill: no coupons, its value grows smoothly up to the face value
        times = [years * i / 12 for i in range(13)]
        values = [bond_price(y, 0, years - t, face=face) for t in times]
    else:
        times = [i / 2 for i in range(n_coupons + 1)]    # 0, 0.5, 1, 1.5 ... years
        values = [amount + each_coupon * i for i in range(n_coupons + 1)]
    gain_pct = [(v - amount) / amount * 100 for v in values]

    return {"y": y, "years": years, "price": price, "face": face, "each_coupon": each_coupon,
            "final": final, "interest": interest, "times": times, "gain_pct": gain_pct}

#Charts
def draw_charts(amount, bond, result):
    fig.clear()
    grid = fig.add_gridspec(2, 2, height_ratios=[1, 1.2])
    ax_yield = fig.add_subplot(grid[0, 0])
    ax_price = fig.add_subplot(grid[0, 1])
    ax_money = fig.add_subplot(grid[1, :])               # bottom chart uses the full width

    #Top charts: all 3 bonds, the selected one drawn thicker
    for name in MATURITY_YEARS:
        width = 2.5 if name == bond else 1
        ax_yield.plot(data.index, data[name], label=name, lw=width)
        ax_price.plot(prices.index, prices[name], label=name, lw=width)
    ax_yield.set_title("Yield (%)")
    ax_price.set_title(f"Price of a bond bought at $100 {HISTORY_YEARS} years ago")
    for ax in (ax_yield, ax_price):
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

    #Bottom chart: how your money grows until the bond matures
    in_months = result["years"] < 1
    x = [t * 12 for t in result["times"]] if in_months else result["times"]
    gain = result["gain_pct"]
    color = f"C{list(MATURITY_YEARS).index(bond)}"      # same color as the bond's line above

    if result["each_coupon"] == 0:                       # T-bill: smooth line
        ax_money.plot(x, gain, color=color, lw=2.5)
        ax_money.fill_between(x, gain, color=color, alpha=0.15)
    else:                                                # coupon bond: a step up every 6 months
        ax_money.step(x, gain, where="post", color=color, lw=2.5)
        ax_money.fill_between(x, gain, step="post", color=color, alpha=0.15)
    ax_money.set_title(f"Your ${amount:,.0f} in {bond} until it matures")
    ax_money.set_xlabel("Months from today" if in_months else "Years from today")
    ax_money.set_ylabel("Total gain")
    ax_money.yaxis.set_major_formatter(PercentFormatter())
    ax_money.set_xlim(0, x[-1])
    ax_money.set_ylim(0, max(gain[-1], 0.01) * 1.25)
    ax_money.grid(alpha=0.3)

    #Right-hand axis: the same line shown in dollars
    dollars = ax_money.secondary_yaxis("right", functions=(
        lambda pct: amount * (1 + pct / 100),
        lambda value: (value / amount - 1) * 100))
    dollars.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:,.0f}"))
    dollars.set_ylabel("Your money")

    ax_money.annotate(f"+{gain[-1]:.2f}%\n${result['final']:,.2f}",
                      xy=(x[-1], gain[-1]), xytext=(-10, 8), textcoords="offset points",
                      ha="right", va="bottom", fontsize=12, fontweight="bold", color=color)
    canvas.draw()

#What happens when you press Calculate, press Enter or pick a bond
def on_calculate(event=None):
    try:
        amount = float(amount_var.get().replace(",", "").replace("$", ""))
    except ValueError:
        messagebox.showerror("Invalid amount", "Please type a number, like 10000.")
        return
    if amount <= 0:
        messagebox.showerror("Invalid amount", "The amount must be more than 0.")
        return

    bond = bond_var.get()
    result = calculate(amount, bond)
    maturity = data.index[-1] + pd.DateOffset(months=round(result["years"] * 12))
    coupon_text = "none (T-bill)" if result["each_coupon"] == 0 else f"${result['each_coupon']:,.2f}"

    final_label.config(text=f"${result['final']:,.2f}")
    gain_label.config(text=f"+{result['gain_pct'][-1]:.2f}% after {duration_text(result['years'])}")
    profit_label.config(text=f"+${result['interest']:,.2f} profit")
    details_label.config(text=
        f"Yield today     {result['y']:.2f}%\n"
        f"Price           {result['price']:.2f} per $100\n"
        f"Face value      ${result['face']:,.2f}\n"
        f"Coupon / 6 mo   {coupon_text}\n"
        f"Interest        ${result['interest']:,.2f}\n"
        f"Matures         {maturity:%d %b %Y}\n"
        f"Yields as of    {data.index[-1]:%d %b %Y}")
    draw_charts(amount, bond, result)

#App window
FONT = "Segoe UI"
root = tk.Tk()
root.title("Bond Calculator")
root.configure(bg="white")
root.geometry("1500x900")

panel = tk.Frame(root, bg="white", padx=25, pady=25)
panel.pack(side="left", fill="y")

tk.Label(panel, text="Bond Calculator", font=(FONT, 18, "bold"), bg="white").pack(anchor="w")

tk.Label(panel, text="Amount to invest ($)", font=(FONT, 10), bg="white").pack(anchor="w", pady=(25, 2))
amount_var = tk.StringVar(value="10000")
tk.Entry(panel, textvariable=amount_var, font=(FONT, 13), width=14).pack(anchor="w")

tk.Label(panel, text="Bond", font=(FONT, 10), bg="white").pack(anchor="w", pady=(20, 2))
bond_var = tk.StringVar(value="US10Y")
for name, years in MATURITY_YEARS.items():
    tk.Radiobutton(panel, text=f"{name}  ({duration_text(years)})", variable=bond_var, value=name,
                   command=on_calculate, font=(FONT, 11), bg="white", activebackground="white").pack(anchor="w")

tk.Button(panel, text="Calculate", command=on_calculate, font=(FONT, 11, "bold"),
          padx=15, pady=4).pack(anchor="w", pady=20)

tk.Label(panel, text="You get back", font=(FONT, 10), bg="white", fg="gray").pack(anchor="w")
final_label = tk.Label(panel, font=(FONT, 24, "bold"), bg="white")
final_label.pack(anchor="w")
gain_label = tk.Label(panel, font=(FONT, 12), bg="white", fg="black")       # % gain, normal text
gain_label.pack(anchor="w")
profit_label = tk.Label(panel, font=(FONT, 14, "bold"), bg="white", fg="green")  # money gained, green
profit_label.pack(anchor="w")
details_label = tk.Label(panel, font=("Consolas", 10), bg="white", justify="left")
details_label.pack(anchor="w", pady=(20, 0))

tk.Label(panel, text="Assumes you buy a new bond today, hold it until it matures, "
                     "and don't reinvest the coupons. Taxes are ignored.",
         font=(FONT, 9), bg="white", fg="gray", wraplength=240, justify="left").pack(anchor="w", side="bottom")

fig = Figure(figsize=(11, 8), facecolor="white", layout="constrained")
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(side="right", fill="both", expand=True)

root.bind("<Return>", on_calculate)                    # pressing Enter also calculates
on_calculate()                                         # show the default result on start
root.mainloop()
