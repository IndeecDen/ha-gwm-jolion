package ru.jolion.locator;

import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import javax.crypto.Cipher;
import javax.crypto.spec.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=27,manifest=Config.NONE)
public class DiskTransportTest {
    private String key="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    private JSONObject decrypt(byte[] body) throws Exception {
        JSONObject envelope=new JSONObject(new String(body,StandardCharsets.UTF_8));
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,new SecretKeySpec(MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8)),"AES"),new GCMParameterSpec(128,Base64.getDecoder().decode(envelope.getString("nonce"))));
        cipher.updateAAD("jolion-disk-v1:jolion".getBytes(StandardCharsets.UTF_8));
        return new JSONObject(new String(cipher.doFinal(Base64.getDecoder().decode(envelope.getString("ciphertext"))),StandardCharsets.UTF_8));
    }
    private JSONArray points() throws Exception {return new JSONArray().put(new JSONObject().put("id","point-000000001").put("latitude",55.75));}
    @Test public void readsPythonFixtureAndUsesUniqueNonces() throws Exception {
        try(java.io.InputStream in=getClass().getResourceAsStream("/disk-batch.json")) {
            java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();byte[] b=new byte[1024];int n;while((n=in.read(b))!=-1)out.write(b,0,n);
            assertEquals(55.75,decrypt(out.toByteArray()).getJSONArray("points").getJSONObject(0).getDouble("latitude"),0);
        }
        byte[] a=DiskTransport.encrypt(points(),"jolion",key),b=DiskTransport.encrypt(points(),"jolion",key);
        assertFalse(Arrays.equals(a,b));assertEquals(55.75,decrypt(a).getJSONArray("points").getJSONObject(0).getDouble("latitude"),0);
        assertFalse(new String(a,StandardCharsets.UTF_8).contains(key));
    }
    @Test public void uploadsHistoryAndLatestWithoutForwardingOauth() throws Exception {
        List<String> urls=new ArrayList<>();List<byte[]> bodies=new ArrayList<>();
        DiskTransport transport=new DiskTransport((url,method,token,body)->{
            urls.add(url);
            if(method.equals("GET")){assertEquals("oauth-secret",token);assertTrue(url.startsWith(DiskTransport.API));return "{\"href\":\"https://uploader.disk.yandex.net/upload\",\"method\":\"PUT\"}".getBytes(StandardCharsets.UTF_8);}
            assertNull(token);bodies.add(body);return new byte[0];
        });
        transport.send(new QueueDb.Batch("yadisk:/JolionLocator","jolion",key,points()),"oauth-secret");
        assertEquals(4,urls.size());assertTrue(urls.get(2).contains("latest-jolion.jloc"));assertArrayEquals(bodies.get(0),bodies.get(1));decrypt(bodies.get(0));
    }
    @Test public void failedUploadPropagatesAndDoesNotReportSuccess() throws Exception {
        DiskTransport transport=new DiskTransport((url,method,token,body)->{throw new java.io.IOException("offline");});
        try{transport.send(new QueueDb.Batch("yadisk:/JolionLocator","jolion",key,points()),"oauth");fail();}catch(java.io.IOException expected){}
    }
    @Test public void rejectsUnsafeUploadUrlsAndFolders() throws Exception {
        for(String url:new String[]{"http://yandex.ru/a","https://yandex.ru.attacker.test/a","https://user@yandex.ru/a","https://127.0.0.1/a"}) {
            try{DiskTransport.safeUrl(url);fail(url);}catch(java.io.IOException expected){}
        }
        assertTrue(DiskTransport.validFolder("/JolionLocator"));assertFalse(DiskTransport.validFolder("/../Other"));
    }
}
