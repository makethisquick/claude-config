#!/usr/bin/env python3
"""Render the report's charts from the pull_data.py blob.

Run with a python that has matplotlib: ~/.claude/skills/client-launch/.venv/bin/python

Only charts that the data actually supports are written; build_docx.js includes
whichever exist. A chart of an empty metric is worse than no chart — it invites
the client to read meaning into noise.
"""
import argparse, json, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

def style(accent):
    DARK="1F2430"
    plt.rcParams.update({"font.family":"DejaVu Sans","axes.edgecolor":"#D6D9E3",
        "axes.labelcolor":"#"+DARK,"text.color":"#"+DARK,"xtick.color":"#8A92A6","ytick.color":"#8A92A6",
        "axes.spines.top":False,"axes.spines.right":False,"figure.dpi":200})

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data",required=True); ap.add_argument("--out",required=True)
    ap.add_argument("--accent",default="#E31A1C")
    ap.add_argument("--lead-noun",default="enquiry",help="what one lead is called on chart titles, e.g. 'call tap'")
    a=ap.parse_args(); os.makedirs(a.out,exist_ok=True)
    d=json.load(open(a.data)); style(a.accent)
    ACCENT=a.accent; LIGHT="#E8EAF0"; GREY="#8A92A6"; DARK="#1F2430"; GREEN="#1B8A5A"; MID="#F4A8A9"
    W=d["windows"]; made=[]
    labels=[f"{w['label']}\n{w['start'][5:].replace('-','/')}–{w['end'][5:].replace('-','/')}" for w in W]

    # 1 — lead rate per window
    if len(W)>1 and any(w["leads"] for w in W):
        cvr=[w["cvr"] for w in W]; leads=[w["leads"] for w in W]
        fig,ax=plt.subplots(figsize=(7.2,3.1))
        cols=[LIGHT]*(len(W)-1)+[ACCENT]
        if len(W)==3: cols=[LIGHT,MID,ACCENT]
        b=ax.bar(labels,cvr,color=cols,width=.55,zorder=3)
        top=max(cvr) if max(cvr)>0 else 1
        ax.set_ylabel("Enquiries per 100 visits"); ax.set_ylim(0,top*1.38)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f"{v:.0f}%")); ax.grid(axis="y",color=LIGHT,zorder=0)
        for bb,c,l in zip(b,cvr,leads):
            x=bb.get_x()+bb.get_width()/2; n=int(l); lab=f"{n} enquir{'y' if n==1 else 'ies'}"
            if c < top*0.16:   # keep the two labels off each other on a near-zero bar
                ax.text(x,top*0.085,f"{c:.2f}%",ha="center",fontweight="bold",fontsize=11,color=DARK)
                ax.text(x,top*0.030,lab,ha="center",fontsize=9,color=GREY,fontweight="bold")
            else:
                ax.text(x,c+top*0.045,f"{c:.2f}%",ha="center",fontweight="bold",fontsize=11,color=DARK)
                ax.text(x,c/2,lab,ha="center",fontsize=9,color="white",fontweight="bold")
        ax.set_title("Enquiries per 100 visits",loc="left",fontweight="bold",fontsize=13,pad=10)
        plt.tight_layout(); plt.savefig(f"{a.out}/c1_leadrate.png",bbox_inches="tight"); plt.close(); made.append("c1_leadrate.png")

    # 2 — cost per enquiry
    pts=[(i,w["cpl"]) for i,w in enumerate(W) if w.get("cpl")]
    if len(pts)>=2:
        fig,ax=plt.subplots(figsize=(7.2,3.0))
        ax.plot([p[0] for p in pts],[p[1] for p in pts],color=ACCENT,lw=3,marker="o",ms=9,zorder=3)
        ax.set_xticks(range(len(W))); ax.set_xticklabels(labels)
        hi=max(p[1] for p in pts); ax.set_ylim(0,hi*1.35); ax.set_ylabel("Cost per enquiry")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f"${v:.0f}")); ax.grid(axis="y",color=LIGHT,zorder=0)
        for i,(x,y) in enumerate(pts):
            good = i==len(pts)-1 and y==min(p[1] for p in pts)
            ax.annotate(f"${y:.0f}",(x,y),textcoords="offset points",xytext=(0,13),ha="center",
                        fontweight="bold",fontsize=12 if good else 10,color=GREEN if good else DARK)
        for i,w in enumerate(W):
            if not w.get("cpl"): ax.text(i,hi*1.1,"no enquiries yet",ha="center",color=GREY,fontsize=9,style="italic")
        ax.set_title(f"Cost per {a.lead_noun}",loc="left",fontweight="bold",fontsize=13,pad=10)
        plt.tight_layout(); plt.savefig(f"{a.out}/c2_cpl.png",bbox_inches="tight"); plt.close(); made.append("c2_cpl.png")

    # 3 — visitor behaviour, only if GA4 gave us both ends
    g=d.get("ga4") or {}
    if g.get("first") and g.get("latest"):
        f0,l0=g["first"],g["latest"]
        fig,axes=plt.subplots(1,2,figsize=(7.2,2.9))
        for ax,(t,b4,af,fmt,note) in zip(axes,[
            ("Visitors who leave immediately",f0["bounce"],l0["bounce"],"{:.0f}%","lower is better"),
            ("Time spent on your site",f0["avg_session_s"],l0["avg_session_s"],"{:.0f}s","higher is better")]):
            bars=ax.bar(["Before","After"],[b4,af],width=.5,zorder=3)
            improved = (af<b4) if "lower" in note else (af>b4)
            bars[0].set_color(LIGHT); bars[1].set_color(GREEN if improved else ACCENT)
            ax.set_title(t,loc="left",fontsize=10.5,fontweight="bold",pad=8)
            ax.text(0.5,-0.22,note,transform=ax.transAxes,ha="center",fontsize=8.5,color=GREY,style="italic")
            ax.set_ylim(0,max(b4,af)*1.32); ax.grid(axis="y",color=LIGHT,zorder=0); ax.set_yticks([])
            for bb,v in zip(bars,[b4,af]):
                ax.text(bb.get_x()+bb.get_width()/2,v+max(b4,af)*0.045,fmt.format(v),ha="center",fontweight="bold",color=DARK)
        plt.tight_layout(); plt.savefig(f"{a.out}/c3_behaviour.png",bbox_inches="tight"); plt.close(); made.append("c3_behaviour.png")

    # 4 — daily spend vs the planned budget
    if len(W)>1:
        sp=[w["per_day"] for w in W]; budget=d.get("budget_per_day_total")
        fig,ax=plt.subplots(figsize=(7.2,2.6))
        cols=[LIGHT]*(len(W)-1)+[ACCENT]
        if len(W)==3: cols=[LIGHT,"#C9CEDC",ACCENT]
        ax.bar(labels,sp,color=cols,width=.5,zorder=3)
        hi=max(sp+([budget] if budget else []))
        if budget:
            ax.axhline(budget,color=DARK,ls="--",lw=1.4,zorder=4)
            # label sits in the headroom, not on the line — a bar near budget would collide with it
            ax.text(len(W)-0.5,hi*1.22,f"- - -  planned budget ${budget:,.2f}/day",fontsize=8.5,color=DARK,ha="right",va="center")
        ax.set_ylabel("Average daily spend"); ax.set_ylim(0,hi*1.3)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f"${v:,.0f}")); ax.grid(axis="y",color=LIGHT,zorder=0)
        for i,v in enumerate(sp):   # value at mid-bar: spend usually sits near the budget line
            ax.text(i,v/2,f"${v:,.2f}",ha="center",va="center",fontweight="bold",fontsize=10,
                    color="white" if i==len(sp)-1 else DARK)
        ax.set_title("Average daily spend",loc="left",fontweight="bold",fontsize=13,pad=10)
        plt.tight_layout(); plt.savefig(f"{a.out}/c4_spend.png",bbox_inches="tight"); plt.close(); made.append("c4_spend.png")

    print(json.dumps({"charts": made, "dir": a.out}, indent=1))

if __name__=="__main__": main()
