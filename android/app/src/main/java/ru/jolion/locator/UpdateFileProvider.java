package ru.jolion.locator;

import android.content.*;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.File;
import java.io.IOException;

/** Minimal FileProvider for the locally downloaded update APK. */
public final class UpdateFileProvider extends ContentProvider {
    public boolean onCreate(){return true;}
    private File file(Uri uri){
        try {
            File root=new File(getContext().getCacheDir(),"updates").getCanonicalFile();
            File f=new File(root,uri.getPath()==null?"":uri.getPath().replaceFirst("^/","")).getCanonicalFile();
            if(!f.getPath().startsWith(root.getPath()+File.separator))throw new SecurityException("outside update cache");
            return f;
        } catch(IOException error) { throw new SecurityException("invalid update path",error); }
    }
    public String getType(Uri uri){return "application/vnd.android.package-archive";}
    public ParcelFileDescriptor openFile(Uri uri,String mode)throws java.io.FileNotFoundException{if(!"r".equals(mode))throw new SecurityException("read only");return ParcelFileDescriptor.open(file(uri),ParcelFileDescriptor.MODE_READ_ONLY);}
    public Cursor query(Uri uri,String[] projection,String s,String[] a,String sort){File f=file(uri);MatrixCursor c=new MatrixCursor(new String[]{"_display_name","_size"});c.addRow(new Object[]{f.getName(),f.length()});return c;}
    public int delete(Uri u,String s,String[] a){return 0;} public int update(Uri u,ContentValues v,String s,String[] a){return 0;} public Uri insert(Uri u,ContentValues v){return null;}
}
