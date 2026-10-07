package ru.jolion.locator;

import android.content.Context;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import static org.junit.Assert.*;

/** Entire download pipeline uses in-memory HTTP replies, never GitHub. */
@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=27, manifest=org.robolectric.annotation.Config.NONE)
public class UpdateDownloadTest {
    private Context context;
    private final byte[] apk="local apk fixture".getBytes(StandardCharsets.UTF_8);
    private String hash;
    private final List<Reply> replies=new ArrayList<>();
    private static class Reply extends HttpURLConnection {
        final byte[] bytes; final int status; final long length; boolean disconnected;
        Reply(URL u,byte[] b,int s,long l){super(u);bytes=b;status=s;length=l;}
        public void connect(){} public boolean usingProxy(){return false;}
        public void disconnect(){disconnected=true;}
        public int getResponseCode(){return status;}
        public long getContentLengthLong(){return length;}
        public InputStream getInputStream(){return new ByteArrayInputStream(bytes);}
    }
    @Before public void setup() throws Exception {
        context=RuntimeEnvironment.getApplication();
        File dir=new File(context.getCacheDir(),"updates");dir.mkdirs();
        for(File file:dir.listFiles())assertTrue(file.delete());
        StringBuilder text=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(apk))text.append(String.format("%02x",b&255));hash=text.toString();
    }
    private UpdateChecker.Release release(long size){return new UpdateChecker.Release("1.0.0","","https://local/apk","https://local/sums","Jolion релиз.apk",size);}
    private UpdateChecker.ConnectionFactory server(String checksum,int status,long length){
        return url->{boolean sums=url.getPath().equals("/sums");byte[] bytes=sums?checksum.getBytes(StandardCharsets.UTF_8):apk;
            Reply reply=new Reply(url,bytes,sums?200:status,sums?bytes.length:length);replies.add(reply);return reply;};
    }
    private String sums(){return hash+"  Jolion релиз.apk\n";}
    private void assertClean(){assertEquals(0,new File(context.getCacheDir(),"updates").list().length);for(Reply r:replies)assertTrue(r.disconnected);}
    @Test public void validatesOriginalAssetNameAndFinalizesOnlyVerifiedFile() throws Exception {
        File file=UpdateChecker.download(context,release(apk.length),null,server(sums(),200,apk.length),f->Arrays.equals(apk,java.nio.file.Files.readAllBytes(f.toPath())));
        assertTrue(file.getName().endsWith(".apk"));assertEquals(hash,UpdateChecker.sha256(file));
        for(Reply r:replies)assertTrue(r.disconnected);
    }
    @Test public void rejectsCorruptChecksumAndDeletesPartialFile() {
        assertThrows(SecurityException.class,()->UpdateChecker.download(context,release(apk.length),null,server(sums().replace(hash,"0".repeat(64)),200,apk.length),f->{fail("unverified APK inspected");return true;}));
        assertClean();
    }
    @Test public void rejectsTruncatedHttpResponseEvenWithoutReleaseSize() {
        assertThrows(SecurityException.class,()->UpdateChecker.download(context,release(0),null,server(sums(),200,apk.length+1),f->true));assertClean();
    }
    @Test public void rejectsIncompatiblePackageAndCleansUp() {
        assertThrows(SecurityException.class,()->UpdateChecker.download(context,release(apk.length),null,server(sums(),200,apk.length),f->false));assertClean();
    }
    @Test public void disconnectsOnHttpFailureAndRejectsHttpBeforeConnecting() {
        assertThrows(IOException.class,()->UpdateChecker.download(context,release(apk.length),null,server(sums(),503,apk.length),f->true));assertClean();
        assertThrows(SecurityException.class,()->UpdateChecker.get("http://local/releases"));
    }
}
