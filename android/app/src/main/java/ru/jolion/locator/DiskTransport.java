package ru.jolion.locator;

import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import javax.crypto.Cipher;
import javax.crypto.spec.*;
import javax.net.ssl.HttpsURLConnection;

/** Encrypted, immutable history batches plus a replaceable live snapshot. */
final class DiskTransport {
    static final String API="https://cloud-api.yandex.net/v1/disk/resources/upload";
    interface Client { byte[] request(String url,String method,String token,byte[] body) throws Exception; }
    private final Client client;
    DiskTransport() { this(DiskTransport::http); }
    DiskTransport(Client client) { this.client=client; }
    static String digest(byte[] bytes) throws Exception {
        StringBuilder s=new StringBuilder();
        for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))s.append(String.format("%02x",b&255));
        return s.toString();
    }
    static byte[] encrypt(JSONArray points,String vehicle,String key) throws Exception {
        byte[] nonce=new byte[12];new SecureRandom().nextBytes(nonce);
        return encrypt(points,vehicle,key,nonce);
    }
    static byte[] encrypt(JSONArray points,String vehicle,String key,byte[] nonce) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE,new SecretKeySpec(MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8)),"AES"),new GCMParameterSpec(128,nonce));
        cipher.updateAAD(("jolion-disk-v1:"+vehicle).getBytes(StandardCharsets.UTF_8));
        byte[] plain=new JSONObject().put("version",1).put("points",points).toString().getBytes(StandardCharsets.UTF_8);
        return new JSONObject().put("version",1).put("vehicle_id",vehicle).put("nonce",Base64.getEncoder().encodeToString(nonce))
            .put("ciphertext",Base64.getEncoder().encodeToString(cipher.doFinal(plain))).toString().getBytes(StandardCharsets.UTF_8);
    }
    static String safeUrl(String value) throws Exception {
        URI uri=new URI(value);String host=uri.getHost();
        if(!"https".equals(uri.getScheme()) || host==null || uri.getUserInfo()!=null || (uri.getPort()!=-1 && uri.getPort()!=443))throw new IOException("Untrusted URL");
        boolean allowed=false;
        for(String domain:new String[]{"yandex.ru","yandex.net","yandex.com"})if(host.equals(domain)||host.endsWith("."+domain))allowed=true;
        if(!allowed)throw new IOException("Untrusted URL");return value;
    }
    static boolean validFolder(String path) {
        return path!=null && path.matches("/[A-Za-z0-9_-]{1,80}");
    }
    void send(QueueDb.Batch batch,String oauth) throws Exception {
        String folder=batch.base.substring("yadisk:".length());
        if(!validFolder(folder)||oauth.isEmpty())throw new IOException("Disk settings required");
        List<String> ids=new ArrayList<>();
        for(int i=0;i<batch.points.length();i++)ids.add(batch.points.getJSONObject(i).getString("id"));
        Collections.sort(ids);
        String name=batch.vehicle+"-"+digest(String.join("\n",ids).getBytes(StandardCharsets.UTF_8))+".jloc";
        byte[] body=encrypt(batch.points,batch.vehicle,batch.token);
        put(folder+"/"+name,oauth,body);
        put(folder+"/latest-"+batch.vehicle+".jloc",oauth,body);
    }
    private void put(String path,String oauth,byte[] body) throws Exception {
        String url=API+"?overwrite=true&path="+URLEncoder.encode("disk:"+path,"UTF-8");
        JSONObject link=new JSONObject(new String(client.request(url,"GET",oauth,null),StandardCharsets.UTF_8));
        if(!"PUT".equals(link.optString("method","PUT")))throw new IOException("Unexpected upload method");
        client.request(safeUrl(link.getString("href")),"PUT",null,body);
    }
    static byte[] http(String url,String method,String token,byte[] body) throws Exception {
        safeUrl(url);
        if(token!=null && !url.startsWith(API+"?"))throw new IOException("OAuth destination rejected");
        HttpsURLConnection c=(HttpsURLConnection)new URL(url).openConnection();
        try {
            c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(20000);c.setRequestMethod(method);
            if(token!=null)c.setRequestProperty("Authorization","OAuth "+token);
            if(body!=null){c.setDoOutput(true);c.setFixedLengthStreamingMode(body.length);c.setRequestProperty("Content-Type","application/octet-stream");try(OutputStream out=c.getOutputStream()){out.write(body);}}
            int code=c.getResponseCode();
            if(code!=200 && code!=201)throw new IOException("Disk HTTP "+code);
            ByteArrayOutputStream result=new ByteArrayOutputStream();
            try(InputStream in=c.getInputStream()) {
                byte[] buf=new byte[4096];int n;
                while((n=in.read(buf))!=-1){if(result.size()+n>65536)throw new IOException("Response too large");result.write(buf,0,n);}
            }
            return result.toByteArray();
        } finally {c.disconnect();}
    }
}
