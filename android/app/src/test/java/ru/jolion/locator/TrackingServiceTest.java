package ru.jolion.locator;

import org.junit.Test;
import org.junit.runner.RunWith;
import android.location.Location;
import org.robolectric.RobolectricTestRunner;
import static org.junit.Assert.*;

/**
 * The satellite receiver is precise but slow to lock after a cold start; the
 * network provider reports a coarse position in seconds. The coarse fixes fill the
 * start of the track and must be dropped the moment GPS locks, otherwise the morning
 * route either starts minutes late or is smeared with kilometre-scale jumps.
 */
@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk = 27)
public class TrackingServiceTest {

    @Test public void gpsIsAcceptedUpToItsPrecisionCap() {
        assertTrue(TrackingService.acceptProvider("gps", 100f, false));
        assertTrue(TrackingService.acceptProvider("gps", 100f, true));
        assertFalse("GPS свыше 100 м — мусор", TrackingService.acceptProvider("gps", 101f, false));
    }

    @Test public void networkBridgesTheColdStartUntilGpsLocks() {
        // Пока спутник ловит, грубая сетевая точка заполняет начало трека.
        assertTrue(TrackingService.acceptProvider("network", 1500f, false));
        assertTrue(TrackingService.acceptProvider("network", 800f, false));
        // После захвата GPS сетевые точки только размажут маршрут.
        assertFalse(TrackingService.acceptProvider("network", 50f, true));
        assertFalse(TrackingService.acceptProvider("network", 1500f, true));
    }

    @Test public void networkIsRejectedBeyondTheCoarseCap() {
        assertFalse(TrackingService.acceptProvider("network", 1501f, false));
    }

    @Test public void networkMayReportOnlyDuringGpsLossRecovery() {
        assertFalse(TrackingService.acceptProvider("network", 500f, true));
        assertTrue(TrackingService.acceptProvider("network", 500f, true, true));
    }

    private Location gps(long time, double lat, double lon) {
        Location location = new Location("gps");
        location.setTime(time);
        location.setLatitude(lat);
        location.setLongitude(lon);
        location.setAccuracy(10f);
        return location;
    }

    @Test public void duplicateAndTinyJitterAreDropped() {
        Location first = gps(1_700_000_000_000L, 55.75, 37.62);
        assertFalse(TrackingService.transitionAllowed(first, gps(first.getTime(), 55.75, 37.62)));
        assertFalse(TrackingService.transitionAllowed(first, gps(first.getTime()+1000, 55.750005, 37.62)));
    }

    @Test public void impossibleJumpIsDroppedButLongGapResetsTheFilter() {
        Location first = gps(1_700_000_000_000L, 55.75, 37.62);
        Location jump = gps(first.getTime()+1000, 55.80, 37.62);
        assertFalse(TrackingService.transitionAllowed(first, jump));
        Location afterGap = gps(first.getTime()+120_001, 55.80, 37.62);
        assertTrue(TrackingService.transitionAllowed(first, afterGap));
    }

    @Test public void normalMovementIsAccepted() {
        Location first = gps(1_700_000_000_000L, 55.75, 37.62);
        assertTrue(TrackingService.transitionAllowed(first, gps(first.getTime()+2000, 55.7501, 37.62)));
    }
}
