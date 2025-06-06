# DMVApptChecker

## DMV Appt Scraper

I created this script b/c the NC DMV appointment system SUCKS!

## This isn't for just anyone.  If you are not SUPER comfortable with python code and command line scripts - don't even start. 

## Use this guy's website instead and be sure to slip him a coffee.

### https://nc-dmv-appointments.com/

## No guarantees that this code won't corrupt your computer.
## No guarantee it won't get you in trouble with the DMV.
## No guarantee it won't bork an existing appointment you already have (it won't but still - no guarantee!)

My operating conditions.

1) Running on a Mac OS desktop
2) Xtools and command line stuff including Python3 installed
3) Playwright and Chromium installed
4) I am using Mac OS desktop alerts and a webhook push to my Home Assistant instance - you will need to decide what notification method you want.
5) You will need to input your location Lat/Long into the script - it doesn't read from a file.
6) This is all made to run from whatever directory you put it in.  References to subdirectories are ./Logs and ./Screenshots so it shouldn't matter where you run it.
7) Even though Playwright will run headless - if you want to snag an appointment it found and you are running headless, you have to re-launch the browser in a non-headless state so you can interact.  I didn't want to loose the appointment and I discovered that if you click "Next" to the confirmation page, it temporariliy removes that appointment from anyone else snagging it.  This gave me 3 minutes to get back to my desktop and finalize.

There are 4 mandatory files.

1) checker.py - the workhorse with all the code
2) dmv_loop.sh - a crash recovery and cool down script (will restart checker.py after a random amount of time between 180 and 210 seconds)
3) Limit_distance.txt - if you want to restrict the distance. This is calculated by the DMV.  The Lat/Long is set in the Chromium instance when the user session is started.
4) limit_date.txt - I used this to filter out the 90 day new appointments that are added every day.  Then I used it to progressively walk back until I was able to get an appointment only a day or two away.
5) pause_signal.txt - this was an afterthought.  If you get to a confirmation page and the 3min countdown is running and you are checking on something, you can put the words "skip" or "extend" in this file and the timer loop will pick this up and either add 2 min to the timer or just continue the walk.  I have no idea how long the DMV actually times out the confirmation page.

That's it.  I went from an appointment that was 3 weeks away and 110 miles as the only thing I could manually find - to "next monday" and only 40 min drive.

Check your emails - they cancel on you if you don't follow the instructions exactly.

I was trying to not be too abusive and never got IP banned.  But I did include some random timers.  And it creates a new user session each time it launches the script but then retaains that user session for 60 cycles.
The pause between scan cycles is random between 20-30 seconds and if you hit 60 cycles it will exit the script and the dmv_loop will cool down the script.

Not a fan of the DMV but didn't want to get banned in the 11th hour!

Good luck.

PS - this code SUCKS!  It is bloated, full of debugging statements and probably has a bunch of crazy logic in it.  I didn't write most of it - AI did the heavy lift.  So don't tell me I'm a crappy programmer.  I KNOW!  But it did what I needed it to do.
