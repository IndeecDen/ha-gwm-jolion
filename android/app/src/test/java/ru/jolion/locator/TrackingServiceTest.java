package ru.jolion.locator;

import org.junit.Test;
import org.junit.runner.RunWith;
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
}
