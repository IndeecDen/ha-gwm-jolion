package ru.jolion.locator;

import android.content.Context;
import android.content.pm.ProviderInfo;
import android.net.Uri;
import java.io.File;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=27)
public class UpdateFileProviderTest {
    @Test public void providerRejectsPathTraversalAndWriteMode() throws Exception {
        Context context=RuntimeEnvironment.getApplication();
        UpdateFileProvider provider=new UpdateFileProvider();
        ProviderInfo info=new ProviderInfo();info.authority="ru.jolion.locator.update-provider";info.exported=false;info.grantUriPermissions=true;
        provider.attachInfo(context,info);
        try { provider.query(Uri.parse("content://ru.jolion.locator.update-provider/../escape.apk"),null,null,null,null); fail("traversal accepted"); }
        catch(SecurityException expected) { }
        File dir=new File(context.getCacheDir(),"updates");assertTrue(dir.exists()||dir.mkdirs());File apk=new File(dir,"test.apk");assertTrue(apk.exists()||apk.createNewFile());
        try { provider.openFile(Uri.parse("content://ru.jolion.locator.update-provider/test.apk"),"w"); fail("write accepted"); }
        catch(SecurityException expected) { }
    }
}
