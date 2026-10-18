package com.gathin.tvhome;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Toast;

/** TV-side recovery uses Android's own HOME picker, with no ADB or elevated permission. */
public class RestoreHomeActivity extends Activity {
    private static final String STOCK = "com.dangbei.TVHomeLauncher";
    private static final int PICK_HOME = 41;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) return;
        String label = "索尼原桌面";
        try {
            label = String.valueOf(getPackageManager().getApplicationLabel(
                    getPackageManager().getApplicationInfo(STOCK, 0)));
        } catch (PackageManager.NameNotFoundException ignored) { }
        Toast.makeText(this, "请选择“" + label + "”作为默认主屏幕，选择后按返回键。",
                Toast.LENGTH_LONG).show();
        try {
            startActivityForResult(new Intent(Settings.ACTION_HOME_SETTINGS), PICK_HOME);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "系统未提供默认桌面选择入口。", Toast.LENGTH_LONG).show();
            finish();
        }
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != PICK_HOME) return;
        Intent home = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME);
        ResolveInfo resolved = getPackageManager().resolveActivity(home, PackageManager.MATCH_DEFAULT_ONLY);
        if (resolved != null && resolved.activityInfo != null
                && STOCK.equals(resolved.activityInfo.packageName)) {
            startActivity(new Intent(Intent.ACTION_MAIN).setComponent(new ComponentName(
                    resolved.activityInfo.packageName, resolved.activityInfo.name))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            Toast.makeText(this, "已恢复索尼原桌面", Toast.LENGTH_SHORT).show();
        }
        finish();
    }
}
