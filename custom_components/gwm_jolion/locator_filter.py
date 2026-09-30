"""Conservative display-only stationary lock; raw GPS archive is never edited."""
import math
from math import hypot, cos, radians

# A fix is only as good as its reported accuracy: two fixes that are closer than
# their combined error cannot prove movement. Measured on a real archive, poor
# fixes wander p50 22 m / p90 110 m while parked.
POOR_ACCURACY_M = 10
# Releasing a stationary hold cannot teleport. At 1 Hz a car accelerating from
# rest covers a few metres per tick, so a first step of a hundred metres is a
# false fix, not a departure.
LAUNCH_STEP_M = 25
SPEED_TOLERANCE = 3.0
# Re-emergence after a real signal outage may legitimately be far away, so this
# cap only applies while the previous point was a stationary hold.
UNBOUNDED_SPEED_KMH = 220.0
# At a light or while warming up the engine the receiver reports "nearly stopped"
# with a speed error of 10-20 km/h, so speed proves nothing. On a real archive 556
# of 568 such steps were a 1 m wobble of the receiver, not movement of the car.
MOVING_FLOOR_KMH = 3.0
HOLD_MIN_M = 4.0
HOLD_ACCURACY_FACTOR = 1.5
# A wobble is only held while the coordinates do not yet prove directed movement.
# Once they do, a real slow manoeuvre is drawn again. The window must be long
# enough for confirmed() to reach its 10 m bar, otherwise every slow manoeuvre
# would be frozen at its first few metres.
HOLD_WINDOW = 25


def meters(a,b):
    y=(b['latitude']-a['latitude'])*111195
    x=(b['longitude']-a['longitude'])*111195*cos(radians((a['latitude']+b['latitude'])/2))
    return hypot(x,y)


def moving_speed(point):
    """Two reported error margins are a conservative heuristic, not a guarantee."""
    speed=point.get('speed_kmh')
    error=point.get('speed_accuracy_kmh')
    return speed is not None and speed-2*(error if error is not None else 0)>=1.5


def uncertain_speed(point):
    error=point.get('speed_accuracy_kmh')
    return error is not None and error>0 and not moving_speed(point)


def confirmed(points):
    """Require a sustained, directed displacement, not one noisy speed fix."""
    if len(points)<3:return False
    elapsed=(points[-1]['timestamp_ms']-points[0]['timestamp_ms'])/1000
    if elapsed<2:return False
    accuracy=max(p.get('accuracy_m') or 0 for p in points)
    measured=all(moving_speed(p) for p in points)
    if accuracy>(35 if measured else 25):return False
    if not measured and (len(points)<6 or elapsed<5):return False
    net=meters(points[0],points[-1])
    path=sum(meters(a,b) for a,b in zip(points,points[1:]))
    threshold=max(3,min(12,accuracy*.5)) if measured else max(10,accuracy*1.5)
    return net>=threshold and path>0 and net/path>=.8 and net/elapsed*3.6<=max(25,max(p.get('speed_kmh') or 0 for p in points)*2+10)


def anchored_hold(previous):
    """True when the previous displayed point is a stationary hold.

    Only then is a first step a departure, which cannot be a long jump. After a
    drive the previous point is real, and a re-emergence may be far away.
    """
    return bool(previous.get("display_filtered")) and not (previous.get("speed_kmh") or 0) > 3


def step_limit(previous, p, elapsed, resuming=False):
    """Largest step believable for this fix, in metres.

    The reported speed is the claim being checked, so the limit is derived from
    it instead of trusting the same number that produced the glitch. The single
    exception is the first fix after a signal outage while the car was already
    driving: a tunnel really can end a kilometre away, and that case is proven
    by the following fixes, not by the jump itself.
    """
    if resuming and not anchored_hold(previous):
        return math.inf
    accuracy = p.get("accuracy_m")
    slack = 2.0 + (accuracy if accuracy is not None else 20.0)
    if anchored_hold(previous):
        return max(LAUNCH_STEP_M, slack)
    speed = p.get("speed_kmh")
    if speed is None:
        return slack + UNBOUNDED_SPEED_KMH / 3.6 * elapsed
    return slack + max(0.0, speed) / 3.6 * elapsed * SPEED_TOLERANCE


def declare_gap(out, index):
    """Mark a real break, never one the card would draw as a zero-length dash.

    A hold keeps a position repeated for many ticks, so a rejected point after it
    can sit on the very same spot. Declaring a gap there would fragment the route
    into dozens of zero-length pieces without hiding anything.
    """
    if index <= 0 or index >= len(out):
        return
    previous = out[index - 1]
    if meters(previous, out[index]) <= LAUNCH_STEP_M:
        return
    out[index]["display_break"] = True


def _leg(points):
    out=[dict(p) for p in points]
    if len(points)<3:return out
    stopped=True;start=0;anchor=points[0];pending=[];slow=[];reacquire=[]

    def pin(low,high,at):
        for j in range(low,high):
            out[j].update(latitude=at['latitude'],longitude=at['longitude'],speed_kmh=0,display_filtered=True)

    for i,p in enumerate(points):
        speed=p.get('speed_kmh')
        accuracy=p.get('accuracy_m') if p.get('accuracy_m') is not None else 100
        if stopped:
            anchor_accuracy=anchor.get('accuracy_m')
            if not pending and accuracy<(anchor_accuracy if anchor_accuracy is not None else 100):anchor=p
            plausible=(speed is None or speed>=1.5 or uncertain_speed(p)) and accuracy<=35
            if plausible:pending.append(i)
            else:pending=[]
            pending=pending[-20:]
            if confirmed([points[j] for j in pending]):
                # pending[0] is the first fix that leaves the hold. It was never
                # checked against the anchor, and that is where a false fix used to
                # enter the track as a one-tick teleport. Walk the release and pin
                # anything a car leaving from rest could not have covered.
                release=pending[0]
                skipped=False
                kept={'latitude':anchor['latitude'],'longitude':anchor['longitude'],
                      'speed_kmh':0,'timestamp_ms':anchor['timestamp_ms'],
                      'display_filtered':True}
                for j in pending:
                    candidate=points[j]
                    # The hold may be hours old, but a car leaving from rest covers
                    # a few metres per fix. Judge the step, not the elapsed time.
                    gap=min((candidate['timestamp_ms']-kept['timestamp_ms'])/1000,5.0)
                    if meters(kept,candidate)>step_limit(kept,candidate,gap):
                        skipped=True
                        continue
                    release=j
                    break
                pin(start,release,anchor)
                if skipped:
                    # Some fixes on the way out were not believable from rest. The
                    # receiver jumped, so the car never drove that line: declare the
                    # jump and let the card draw it as a gap.
                    declare_gap(out, release)
                stopped=False;pending=[];slow=[]
        else:
            previous=out[i-1]
            elapsed=(p['timestamp_ms']-previous['timestamp_ms'])/1000
            step=meters(previous,p)
            if (speed is not None and speed<=MOVING_FLOOR_KMH and uncertain_speed(p)
                    and step<=max(HOLD_MIN_M,accuracy*HOLD_ACCURACY_FACTOR)
                    and not confirmed(points[max(start,i-HOLD_WINDOW+1):i+1])):
                # Nearly stopped on a speed reading that proves nothing: a wobble
                # inside the reported accuracy is the receiver, not the car. The
                # step is measured from the last displayed point, so a real creep
                # grows past this radius and lets itself through.
                out[i].update(latitude=previous['latitude'],longitude=previous['longitude'],
                              display_held=True)
                continue
            if accuracy>50 or step>step_limit(previous,p,elapsed):
                out[i].update(latitude=previous['latitude'],longitude=previous['longitude'],speed_kmh=0,display_filtered=True)
                slow=[]
                if accuracy<=35:
                    reacquire.append(i)
                    reacquire=reacquire[-6:]
                    if confirmed([points[j] for j in reacquire]):
                        # Restore one point at a time: a group can contain a false
                        # fix, and dropping the whole group loses a real
                        # re-emergence.
                        kept=out[reacquire[0]-1]
                        for position,j in enumerate(reacquire):
                            candidate=points[j]
                            gap=(candidate['timestamp_ms']-kept['timestamp_ms'])/1000
                            if meters(kept,candidate)>step_limit(kept,candidate,gap,resuming=position==0):
                                continue
                            out[j]=dict(candidate);kept=out[j]
                        declare_gap(out, reacquire[0])
                        reacquire=[]
                else:reacquire=[]
                continue
            reacquire=[]
            uncertain=uncertain_speed(p)
            if (speed is not None and speed<1.5) or uncertain:
                slow.append(i)
                candidates=[points[j] for j in slow]
                noisy=any(uncertain_speed(q) for q in candidates)
                clustered=all(meters(candidates[0],q)<=max(3,min(15,(q.get('accuracy_m') or 0)*.5)) for q in candidates)
                if p['timestamp_ms']-points[slow[0]]['timestamp_ms']>=(15000 if noisy else 5000) and (not noisy or (clustered and not confirmed(candidates))):
                    stopped=True;start=slow[0];anchor=points[start];pending=[]
                elif noisy and (not clustered or confirmed(candidates)):
                    slow=[]
            else:slow=[]
    if stopped:pin(start,len(points),anchor)
    return out


def filter_display(points):
    """Reset on source changes and reception gaps; never infer travel between them."""
    output=[];leg=[];previous=None
    for p in points:
        max_gap=max(30000,p.get('sample_step',1)*2000)
        split=previous and (p['source']!=previous['source'] or p['timestamp_ms']-previous['timestamp_ms']>max_gap)
        if split:
            output.extend(_leg(leg));leg=[]
        item=dict(p)
        if split:item['display_break']=True
        if p['source']=='app':leg.append(item)
        else:output.append(item)
        previous=p
    output.extend(_leg(leg))
    return output
