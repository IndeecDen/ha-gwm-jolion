package ru.jolion.locator;

import org.junit.Test;
import static org.junit.Assert.*;
import com.google.zxing.*;
import com.google.zxing.common.*;
import com.google.zxing.qrcode.*;

public class PairingQrTest {
    @Test public void payloadSurvivesQrRoundTrip() throws Exception {
        String token = "abcdef0123456789abcdef0123456789abcdef0123456789";
        String payload = PairingQr.payload("jolion",token);
        BitMatrix bits = new QRCodeWriter().encode(payload,BarcodeFormat.QR_CODE,600,600);
        int[] pixels = new int[600*600];
        for(int y=0;y<600;y++) for(int x=0;x<600;x++)pixels[y*600+x]=bits.get(x,y)?0:0xffffff;
        Result result = new QRCodeReader().decode(new BinaryBitmap(new HybridBinarizer(new RGBLuminanceSource(600,600,pixels))));
        assertEquals(payload,result.getText());
        assertTrue(result.getText().contains(token));
    }
    @Test(expected=IllegalArgumentException.class) public void rejectInvalidKey(){PairingQr.payload("jolion","short");}
}
