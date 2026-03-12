package com.sahayai.android

import android.Manifest
import android.content.pm.PackageManager
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PermissionsDeclarationTest {

    @Test
    fun manifestDeclaresCoreRuntimePermissions() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val pkgInfo = context.packageManager.getPackageInfo(
            context.packageName,
            PackageManager.PackageInfoFlags.of(PackageManager.GET_PERMISSIONS.toLong())
        )
        val declared = pkgInfo.requestedPermissions?.toSet() ?: emptySet()

        assertTrue(Manifest.permission.RECORD_AUDIO in declared)
        assertTrue(Manifest.permission.CAMERA in declared)
        assertTrue(Manifest.permission.ACCESS_FINE_LOCATION in declared || Manifest.permission.ACCESS_COARSE_LOCATION in declared)
    }
}
