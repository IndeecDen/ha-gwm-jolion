package ru.jolion.locator;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.math.BigInteger;
import java.security.MessageDigest;
import java.util.Locale;

/** GitHub Releases updater. Network access is only made after an explicit UI action. */
final class UpdateChecker {
    static final String RELEASES_URL = "https://api.github.com/repos/IndeecDen/ha-gwm-jolion/releases";
    static final String PACKAGE = "ru.jolion.locator";
    private static final long MAX_APK_BYTES = 100L*1024L*1024L;
    interface Progress { void update(int percent); }
    static final class Release {
        final String version, notes, apkUrl, checksumUrl, apkName;
        final long size;
        Release(String v, String n, String a, String c, String name, long s) { version=v; notes=n; apkUrl=a; checksumUrl=c; apkName=name; size=s; }
    }

    static Release parseRelease(JSONObject json) throws Exception {
        if (json.optBoolean("draft", false)) return null;
        JSONArray assets = json.optJSONArray("assets");
        if (assets == null) return null;
        String apk=null, sums=null, apkName=null; long size=0;
        for (int i=0;i<assets.length();i++) {
            JSONObject asset=assets.getJSONObject(i); String name=asset.optString("name", "");
            if (name.toLowerCase(Locale.US).endsWith(".apk") && name.contains("Jolion")) { apk=asset.optString("browser_download_url", null); apkName=name; size=asset.optLong("size",0); }
            if (name.equalsIgnoreCase("SHA256SUMS.txt")) sums=asset.optString("browser_download_url", null);
        }
        if (apk == null) return null;
        String tag=json.optString("tag_name", "");
        String version=tag.startsWith("v") || tag.startsWith("V") ? tag.substring(1) : tag;
        try { Version.parse(version); } catch (IllegalArgumentException invalid) { return null; }
        return new Release(version, json.optString("body", ""), apk, sums, apkName, size);
    }

    static Release findLatest(String response, boolean includePrerelease) throws Exception {
        JSONArray releases=new JSONArray(response); Release best=null;
        for (int i=0;i<releases.length();i++) {
            JSONObject item=releases.getJSONObject(i);
            if (!includePrerelease && item.optBoolean("prerelease", false)) continue;
            Release candidate=parseRelease(item); if (candidate == null) continue;
            if (!includePrerelease && Version.parse(candidate.version).prerelease != null) continue;
            if (best == null || compareVersions(candidate.version,best.version)>0) best=candidate;
        }
        return best;
    }

    static int compareVersions(String left, String right) {
        Version a=Version.parse(left), b=Version.parse(right);
        for(int i=0;i<3;i++) { int c=new BigInteger(a.numbers[i]).compareTo(new BigInteger(b.numbers[i])); if(c!=0)return c; }
        if(a.prerelease==null && b.prerelease!=null) return 1;
        if(a.prerelease!=null && b.prerelease==null) return -1;
        if(a.prerelease==null) return 0;
        return comparePrerelease(a.prerelease,b.prerelease);
    }

    private static int comparePrerelease(String left,String right) {
        String[] a=left.split("\\.",-1), b=right.split("\\.",-1);
        for(int i=0;i<Math.max(a.length,b.length);i++) {
            if(i>=a.length)return -1; if(i>=b.length)return 1;
            boolean an=a[i].matches("\\d+"), bn=b[i].matches("\\d+");
            if(an && bn) { int c=new BigInteger(a[i]).compareTo(new BigInteger(b[i])); if(c!=0)return c; }
            else if(an!=bn) return an ? -1 : 1;
            else { int c=a[i].compareTo(b[i]); if(c!=0)return c; }
        }
        return 0;
    }

    private static final class Version {
        final String[] numbers; final String prerelease;
        private Version(String[] n,String p){numbers=n;prerelease=p;}
        static Version parse(String value) {
            String clean=value==null?"":value.trim();
            if(clean.startsWith("v")||clean.startsWith("V"))clean=clean.substring(1);
            if(!clean.matches("(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?(\\+[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?"))
                throw new IllegalArgumentException("Invalid release version");
            String[] mainAndPre=clean.split("\\+",2)[0].split("-",2);
            String pre=mainAndPre.length>1?mainAndPre[1]:null;
            if(pre!=null)for(String part:pre.split("\\."))if(part.matches("0[0-9]+"))throw new IllegalArgumentException("Invalid prerelease version");
            return new Version(mainAndPre[0].split("\\."),pre);
        }
    }

    static String sha256(File file) throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256"); byte[] buffer=new byte[8192]; int n;
        try(InputStream in=new BufferedInputStream(new FileInputStream(file))) { while((n=in.read(buffer))!=-1) digest.update(buffer,0,n); }
        StringBuilder out=new StringBuilder(); for(byte b:digest.digest())out.append(String.format(Locale.US,"%02x",b&255)); return out.toString();
    }
    static String installedVersion(Context context) throws Exception {
        return context.getPackageManager().getPackageInfo(PACKAGE, 0).versionName;
    }
    static String checksumFromText(String text, String filename) {
        String found=null;
        for(String line:text.split("\\r?\\n")) {
            String[] p=line.trim().split("\\s+",2);
            if(p.length==2 && p[0].matches("[0-9a-fA-F]{64}")) {
                String name=p[1].startsWith("*")?p[1].substring(1):p[1];
                if(name.equals(filename)) {
                    String hash=p[0].toLowerCase(Locale.US);
                    if(found!=null && !found.equals(hash))return null;
                    found=hash;
                }
            }
        }
        return found;
    }
    static boolean compatibleApk(Context context, File file) throws Exception {
        PackageManager pm=context.getPackageManager();
        PackageInfo candidate=pm.getPackageArchiveInfo(file.getPath(), PackageManager.GET_SIGNATURES);
        PackageInfo installed=pm.getPackageInfo(PACKAGE, PackageManager.GET_SIGNATURES);
        if(candidate==null || installed==null || !PACKAGE.equals(candidate.packageName) || candidate.signatures==null || installed.signatures==null || candidate.signatures.length==0 || installed.signatures.length==0)return false;
        if(candidate.versionCode<=installed.versionCode || candidate.signatures.length!=installed.signatures.length)return false;
        java.util.Set<android.content.pm.Signature> current=new java.util.HashSet<>(java.util.Arrays.asList(installed.signatures));
        return current.equals(new java.util.HashSet<>(java.util.Arrays.asList(candidate.signatures)));
    }
    static String get(String url) throws Exception { return read(url, "application/vnd.github+json"); }
    private static String read(String url,String accept) throws Exception {
        URL endpoint=new URL(url); if(!"https".equalsIgnoreCase(endpoint.getProtocol()))throw new SecurityException("HTTPS required");
        HttpURLConnection c=(HttpURLConnection)endpoint.openConnection(); c.setConnectTimeout(15000);c.setReadTimeout(30000);c.setInstanceFollowRedirects(true);c.setRequestProperty("Accept",accept);c.setRequestProperty("User-Agent","Jolion-Locator-Updater");
        try {
            if(c.getResponseCode()!=200)throw new IOException("HTTP "+c.getResponseCode());
            if(!"https".equalsIgnoreCase(c.getURL().getProtocol()))throw new SecurityException("HTTPS redirect required");
            try(InputStream in=c.getInputStream()){ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(out.size()+n>2*1024*1024)throw new IOException("Response too large");out.write(b,0,n);}return out.toString("UTF-8");}
        } finally {c.disconnect();}
    }
    interface ConnectionFactory { HttpURLConnection open(URL url) throws IOException; }
    interface ApkVerifier { boolean verify(File apk) throws Exception; }

    static File download(Context context, Release release, Progress progress) throws Exception {
        return download(context,release,progress,url -> (HttpURLConnection)url.openConnection(),file -> compatibleApk(context,file));
    }
    static File download(Context context, Release release, Progress progress, ConnectionFactory connections, ApkVerifier verifier) throws Exception {
        if(release.checksumUrl==null)throw new SecurityException("Release has no SHA-256 checksum");
        String expected=checksumFromText(readChecksum(release.checksumUrl,connections),release.apkName);
        if(expected==null)throw new SecurityException("APK checksum not found");
        File dir=new File(context.getCacheDir(),"updates"); if(!dir.exists()&&!dir.mkdirs())throw new IOException("Cannot create update cache");
        URL endpoint=new URL(release.apkUrl);if(!"https".equalsIgnoreCase(endpoint.getProtocol()))throw new SecurityException("APK HTTPS required");
        File file=File.createTempFile("download-",".part",dir);
        HttpURLConnection c=null;
        long done=0;
        try {
            c=connections.open(endpoint);c.setConnectTimeout(15000);c.setReadTimeout(60000);c.setInstanceFollowRedirects(true);c.setRequestProperty("User-Agent","Jolion-Locator-Updater");
            if(c.getResponseCode()!=200)throw new IOException("APK HTTP "+c.getResponseCode());
            if(!"https".equalsIgnoreCase(c.getURL().getProtocol()))throw new SecurityException("APK HTTPS redirect required");
            long declared=c.getContentLengthLong(), total=declared>0?declared:release.size;if(total>MAX_APK_BYTES || release.size>MAX_APK_BYTES)throw new IOException("APK too large");byte[] b=new byte[8192];int n;
            try(InputStream in=c.getInputStream();OutputStream out=new BufferedOutputStream(new FileOutputStream(file))){while((n=in.read(b))!=-1){if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Download cancelled");done+=n;if(done>MAX_APK_BYTES)throw new IOException("APK too large");out.write(b,0,n);if(progress!=null&&total>0)progress.update((int)Math.min(100,done*100/total));}}
            if((declared>=0 && done!=declared) || (release.size>0 && done!=release.size))throw new SecurityException("APK size mismatch");
            if(!expected.equalsIgnoreCase(sha256(file)))throw new SecurityException("APK checksum mismatch");
            if(!verifier.verify(file))throw new SecurityException("APK package, version or signature mismatch");
            if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Download cancelled");
            File verified=new File(dir,file.getName().replace(".part",".apk"));
            if(!file.renameTo(verified))throw new IOException("Cannot finalize update");
            return verified;
        } catch(Exception error) { file.delete(); throw error; }
        finally {if(c!=null)c.disconnect();}
    }
    private static String readChecksum(String url,ConnectionFactory connections) throws Exception {
        URL endpoint=new URL(url);if(!"https".equalsIgnoreCase(endpoint.getProtocol()))throw new SecurityException("HTTPS required");
        HttpURLConnection c=connections.open(endpoint);
        try {
            c.setConnectTimeout(15000);c.setReadTimeout(30000);c.setRequestProperty("User-Agent","Jolion-Locator-Updater");
            if(c.getResponseCode()!=200)throw new IOException("Checksum HTTP "+c.getResponseCode());
            if(!"https".equalsIgnoreCase(c.getURL().getProtocol()))throw new SecurityException("HTTPS redirect required");
            try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()) {
                byte[] buffer=new byte[4096];int n;
                while((n=in.read(buffer))!=-1){if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Download cancelled");if(out.size()+n>65536)throw new IOException("Checksum too large");out.write(buffer,0,n);}
                return out.toString("UTF-8");
            }
        } finally {c.disconnect();}
    }
}
