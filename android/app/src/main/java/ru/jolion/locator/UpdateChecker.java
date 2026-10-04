package ru.jolion.locator;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Locale;

/** GitHub Releases updater. Network access is only made after an explicit UI action. */
final class UpdateChecker {
    static final String RELEASES_URL = "https://api.github.com/repos/IndeecDen/ha-gwm-jolion/releases";
    static final String PACKAGE = "ru.jolion.locator";
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
        String version=tag.startsWith("v") ? tag.substring(1) : tag;
        return new Release(version, json.optString("body", ""), apk, sums, apkName, size);
    }

    static Release findLatest(String response, boolean includePrerelease) throws Exception {
        JSONArray releases=new JSONArray(response); Release best=null;
        for (int i=0;i<releases.length();i++) {
            JSONObject item=releases.getJSONObject(i);
            if (!includePrerelease && item.optBoolean("prerelease", false)) continue;
            Release candidate=parseRelease(item); if (candidate == null) continue;
            if (best == null || compareVersions(candidate.version,best.version)>0) best=candidate;
        }
        return best;
    }

    static int compareVersions(String left, String right) {
        Version a=Version.parse(left), b=Version.parse(right);
        for(int i=0;i<3;i++) if(a.numbers[i]!=b.numbers[i]) return Integer.compare(a.numbers[i],b.numbers[i]);
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
            if(an && bn) { int c=Integer.compare(Integer.parseInt(a[i]),Integer.parseInt(b[i])); if(c!=0)return c; }
            else if(an!=bn) return an ? -1 : 1;
            else { int c=a[i].compareToIgnoreCase(b[i]); if(c!=0)return c; }
        }
        return 0;
    }

    private static final class Version {
        final int[] numbers; final String prerelease;
        private Version(int[] n,String p){numbers=n;prerelease=p;}
        static Version parse(String value) {
            String clean=value==null?"":value.trim();
            if(clean.startsWith("v")||clean.startsWith("V"))clean=clean.substring(1);
            String[] mainAndPre=clean.split("[-+]",2), parts=mainAndPre[0].split("\\.",-1);
            int[] n=new int[]{0,0,0};
            for(int i=0;i<Math.min(3,parts.length);i++) try { n[i]=Integer.parseInt(parts[i]); } catch(NumberFormatException ignored) { }
            return new Version(n,clean.contains("-") ? mainAndPre.length>1 ? mainAndPre[1] : "" : null);
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
        for(String line:text.split("\\r?\\n")) {
            String[] p=line.trim().split("\\s+",2);
            if(p.length==2 && p[0].matches("[0-9a-fA-F]{64}")) {
                if(p[1].replace("*","").endsWith(filename)) return p[0].toLowerCase(Locale.US);
            }
        }
        return null;
    }
    static boolean compatibleApk(Context context, File file) throws Exception {
        PackageManager pm=context.getPackageManager();
        PackageInfo candidate=pm.getPackageArchiveInfo(file.getPath(), PackageManager.GET_SIGNATURES);
        PackageInfo installed=pm.getPackageInfo(PACKAGE, PackageManager.GET_SIGNATURES);
        if(candidate==null || installed==null || !PACKAGE.equals(candidate.packageName) || candidate.signatures==null || installed.signatures==null || candidate.signatures.length==0 || installed.signatures.length==0)return false;
        return MessageDigest.isEqual(candidate.signatures[0].toByteArray(), installed.signatures[0].toByteArray());
    }
    static String get(String url) throws Exception { return read(url, "application/vnd.github+json"); }
    private static String read(String url,String accept) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection(); c.setConnectTimeout(15000);c.setReadTimeout(30000);c.setRequestProperty("Accept",accept);c.setRequestProperty("User-Agent","Jolion-Locator-Updater");
        if(c.getResponseCode()!=200)throw new IOException("HTTP "+c.getResponseCode());
        try(InputStream in=c.getInputStream()){ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);return out.toString("UTF-8");} finally {c.disconnect();}
    }
    static File download(Context context, Release release, Progress progress) throws Exception {
        File dir=new File(context.getCacheDir(),"updates"); if(!dir.exists()&&!dir.mkdirs())throw new IOException("Cannot create update cache");
        String safeName=release.apkName == null ? "Jolion-Locator-"+release.version+".apk" : release.apkName.replaceAll("[^A-Za-z0-9._ -]", "_");
        File file=new File(dir,safeName); HttpURLConnection c=(HttpURLConnection)new URL(release.apkUrl).openConnection();c.setConnectTimeout(15000);c.setReadTimeout(60000);c.setRequestProperty("User-Agent","Jolion-Locator-Updater");
        if(c.getResponseCode()!=200)throw new IOException("APK HTTP "+c.getResponseCode()); long total=c.getContentLengthLong()>0?c.getContentLengthLong():release.size, done=0;byte[] b=new byte[8192];int n;
        try(InputStream in=c.getInputStream();OutputStream out=new BufferedOutputStream(new FileOutputStream(file))){while((n=in.read(b))!=-1){out.write(b,0,n);done+=n;if(progress!=null&&total>0)progress.update((int)Math.min(100,done*100/total));}} finally {c.disconnect();}
        if(release.checksumUrl == null){file.delete();throw new SecurityException("Release has no SHA-256 checksum");}
        String expected=checksumFromText(get(release.checksumUrl), file.getName());
        if(expected == null){file.delete();throw new SecurityException("APK checksum not found");}
        if(!expected.equalsIgnoreCase(sha256(file))){file.delete();throw new SecurityException("APK checksum mismatch");}
        if(!compatibleApk(context,file)){file.delete();throw new SecurityException("APK package or signature mismatch");}
        return file;
    }
}
