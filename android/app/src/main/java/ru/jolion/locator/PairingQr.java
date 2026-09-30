package ru.jolion.locator;

import android.graphics.Bitmap;
import com.google.zxing.BarcodeFormat;
import com.google.zxing.common.BitMatrix;
import com.google.zxing.qrcode.QRCodeWriter;

final class PairingQr {
    static String payload(String id, String key) {
        if (!id.matches("[a-z0-9_-]{1,40}") || !key.matches("[A-Za-z0-9_-]{32,128}")) throw new IllegalArgumentException();
        return "{\"type\":\"golion_locator\",\"version\":1,\"vehicle_id\":\"" + id + "\",\"upload_key\":\"" + key + "\"}";
    }
    static Bitmap bitmap(String id, String key, int size) throws Exception {
        BitMatrix matrix = new QRCodeWriter().encode(payload(id,key), BarcodeFormat.QR_CODE, size, size);
        int[] pixels = new int[size*size];
        for (int y=0;y<size;y++) for(int x=0;x<size;x++) pixels[y*size+x]=matrix.get(x,y)?0xff000000:0xffffffff;
        return Bitmap.createBitmap(pixels,size,size,Bitmap.Config.ARGB_8888);
    }
}
