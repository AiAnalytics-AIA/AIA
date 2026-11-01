# Probíhá a čeká (ActivityTray)

The top bar's count of what is running ("2 běží") and what waits on the person ("1 čeká"). It opens a list:
- every running job, run, render and Deep Research of the place you are in, with its progress in the run's own words ("1 038 z 1 600 AI respondentů");
- every item that waits on you.

Each row links to the step where it is handled.

**Rules**
- A count is never invented. While unread it says "?", never 0.
- A running row shows only what the run reported (`lib/step-activity.ts`), never a percentage the run did not report.
- The coral dot is "čeká na vás" alone. The petrol dot is "běží".
- It reads the same list as the palette's "Čeká na vás" and the overview bar. One source, three views.
- Reduced motion: the running dot does not pulse.
