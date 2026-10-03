// SPDX-License-Identifier: GPL-3.0-only
// Generated from original DEX declarations. Type contracts ONLY; not implementations.
// Regenerate: python3 -m horizon.ui.generate_jni_contract
#pragma once
#include <jni.h>
namespace metaport::shell::contract {
// (Ljava/lang/String;I)V
using nativeAnchorWindow = void (JNICALL *)(JNIEnv*, jclass, jstring, jint);
// (Ljava/lang/String;ZZ)V
using nativeBackgroundDesktop = void (JNICALL *)(JNIEnv*, jclass, jstring, jboolean, jboolean);
// (I)V
using nativeBackgroundWindow = void (JNICALL *)(JNIEnv*, jclass, jint);
// ([Ljava/lang/String;)V
using nativeBroadcastIntent = void (JNICALL *)(JNIEnv*, jclass, jobjectArray);
// ()V
using nativeCloseSystemKeyboard = void (JNICALL *)(JNIEnv*, jclass);
// (IIZ)V
using nativeConfigureSystemKeyboard = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jboolean);
// (Ljava/lang/String;)V
using nativeCreatePortal = void (JNICALL *)(JNIEnv*, jclass, jstring);
// ()V
using nativeDragComplete = void (JNICALL *)(JNIEnv*, jclass);
// (IIILjava/lang/String;)V
using nativeDragShadow = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint, jstring);
// (ILjava/lang/String;)V
using nativeDragStart = void (JNICALL *)(JNIEnv*, jclass, jint, jstring);
// ()Ljava/lang/String;
using nativeDumpsys = jstring (JNICALL *)(JNIEnv*, jclass);
// (IIIILjava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;I)V
using nativeForegroundDesktop = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint, jint, jstring, jstring, jstring, jstring, jstring, jint);
// (Ljava/lang/String;)V
using nativeFrameCommand = void (JNICALL *)(JNIEnv*, jclass, jstring);
// (I)V
using nativeHandleBloomForegroundRequest = void (JNICALL *)(JNIEnv*, jclass, jint);
// (Z)V
using nativeHandleBloomGrabRequest = void (JNICALL *)(JNIEnv*, jclass, jboolean);
// (ILjava/lang/String;)V
using nativeHandleBreadcrumbRequest = void (JNICALL *)(JNIEnv*, jclass, jint, jstring);
// (I)V
using nativeHandleDesktopManagerCloseRequest = void (JNICALL *)(JNIEnv*, jclass, jint);
// (I)V
using nativeHandleDesktopManagerForegroundRequest = void (JNICALL *)(JNIEnv*, jclass, jint);
// ()V
using nativeHandleDesktopManagerHideRequest = void (JNICALL *)(JNIEnv*, jclass);
// (Z)V
using nativeHandleTheaterClientPreferredParams = void (JNICALL *)(JNIEnv*, jclass, jboolean);
// (IZZLjava/lang/String;)V
using nativeHandleTheaterRequestFromPanelId = void (JNICALL *)(JNIEnv*, jclass, jint, jboolean, jboolean, jstring);
// (FZ)V
using nativeHandleUpdateTheaterViewDimming = void (JNICALL *)(JNIEnv*, jclass, jfloat, jboolean);
// (Ljava/lang/String;)V
using nativeHideGazeTooltip = void (JNICALL *)(JNIEnv*, jclass, jstring);
// (III[I)V
using nativeImageViewResponse = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint, jintArray);
// (Lcom/oculus/vrshell/ShellApplication;JLjava/lang/String;Ljava/lang/String;ZZ)J
using nativeInit = jlong (JNICALL *)(JNIEnv*, jclass, jobject, jlong, jstring, jstring, jboolean, jboolean);
// (ILjava/lang/String;)V
using nativeInjectPanelIpc = void (JNICALL *)(JNIEnv*, jclass, jint, jstring);
// (FFFFFFI)V
using nativeJoypadAxis = void (JNICALL *)(JNIEnv*, jclass, jfloat, jfloat, jfloat, jfloat, jfloat, jfloat, jint);
// (IIIIZZZZ)V
using nativeKeyEvent = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint, jint, jboolean, jboolean, jboolean, jboolean);
// (Ljava/lang/String;Ljava/lang/String;IILandroid/graphics/Bitmap;)V
using nativeMaybeUpdatePathwayDestinationMetadata = void (JNICALL *)(JNIEnv*, jclass, jstring, jstring, jint, jint, jobject);
// (Ljava/lang/String;)V
using nativeMemoryPressureUpdate = void (JNICALL *)(JNIEnv*, jclass, jstring);
// (IFFFIFFIZILjava/lang/String;Z)V
using nativeMouse = void (JNICALL *)(JNIEnv*, jclass, jint, jfloat, jfloat, jfloat, jint, jfloat, jfloat, jint, jboolean, jint, jstring, jboolean);
// (IFILjava/lang/String;)V
using nativeNotifyIfsSurfacesChanged = void (JNICALL *)(JNIEnv*, jclass, jint, jfloat, jint, jstring);
// (IFIILhorizonos/graphics/Pose;)V
using nativeNotifySurfaceCalibrationProgress = void (JNICALL *)(JNIEnv*, jclass, jint, jfloat, jint, jint, jobject);
// (IIII)V
using nativeNotifySurfaceKeyboardEvent = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint, jint);
// (IFI)V
using nativeNotifySurfaceTouchpadAudioPlay = void (JNICALL *)(JNIEnv*, jclass, jint, jfloat, jint);
// (Ljava/lang/String;)V
using nativeOnAppInstallCompleted = void (JNICALL *)(JNIEnv*, jclass, jstring);
// (II)V
using nativeOnDensityDpiChanged = void (JNICALL *)(JNIEnv*, jclass, jint, jint);
// ()V
using nativeOnDestroy = void (JNICALL *)(JNIEnv*, jclass);
// (I)V
using nativeOnFocusedPanelChanged = void (JNICALL *)(JNIEnv*, jclass, jint);
// (I)V
using nativeOnInputDeviceAdded = void (JNICALL *)(JNIEnv*, jclass, jint);
// (I)V
using nativeOnInputDeviceRemoved = void (JNICALL *)(JNIEnv*, jclass, jint);
// (ILandroid/os/IBinder;Ljava/lang/String;Landroid/os/Parcel;Ljava/lang/String;III)V
using nativeOnInteractionWindowChanged = void (JNICALL *)(JNIEnv*, jclass, jint, jobject, jstring, jobject, jstring, jint, jint, jint);
// (Ljava/lang/String;Z)V
using nativeOnLaunchContextReady = void (JNICALL *)(JNIEnv*, jclass, jstring, jboolean);
// (Ljava/lang/String;Ljava/lang/String;[Ljava/lang/String;)V
using nativeOnNewObservableChildVolumetricWindow = void (JNICALL *)(JNIEnv*, jclass, jstring, jstring, jobjectArray);
// ([Ljava/lang/String;)V
using nativeOnPersistedVolumetricWindowsRemoved = void (JNICALL *)(JNIEnv*, jclass, jobjectArray);
// (Ljava/lang/String;)V
using nativeOnRemoveChildVolumetricWindow = void (JNICALL *)(JNIEnv*, jclass, jstring);
// (Ljava/lang/String;)V
using nativeOnServiceDisconnected = void (JNICALL *)(JNIEnv*, jclass, jstring);
// (III)V
using nativeOnSizeChanged = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint);
// (Ljava/lang/String;[Ljava/lang/String;)V
using nativeOnVolumetricWindowCreated = void (JNICALL *)(JNIEnv*, jclass, jstring, jobjectArray);
// (IILjava/lang/String;)V
using nativeOpenSystemKeyboard = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jstring);
// (Ljava/lang/String;Ljava/lang/String;)V
using nativePlayEffect = void (JNICALL *)(JNIEnv*, jclass, jstring, jstring);
// (Ljava/lang/String;Ljava/lang/String;IFFFLjava/lang/String;Z)V
using nativePlaySpatialAudio = void (JNICALL *)(JNIEnv*, jclass, jstring, jstring, jint, jfloat, jfloat, jfloat, jstring, jboolean);
// ()V
using nativeRefreshBloomPresentation = void (JNICALL *)(JNIEnv*, jclass);
// (Ljava/lang/String;)V
using nativeRemovePortal = void (JNICALL *)(JNIEnv*, jclass, jstring);
// (Ljava/lang/String;Ljava/lang/String;I)V
using nativeRequestObservableChildVWPoseChange = void (JNICALL *)(JNIEnv*, jclass, jstring, jstring, jint);
// (Z)V
using nativeRequestUpdateGamepadInputMode = void (JNICALL *)(JNIEnv*, jclass, jboolean);
// (I)V
using nativeRequestUpdateRecoveryMonitorId = void (JNICALL *)(JNIEnv*, jclass, jint);
// (Ljava/lang/String;FFF)V
using nativeRequestVWBoundsChange = void (JNICALL *)(JNIEnv*, jclass, jstring, jfloat, jfloat, jfloat);
// (Ljava/lang/String;Ljava/lang/String;)V
using nativeRequestVWLayoutParamsChange = void (JNICALL *)(JNIEnv*, jclass, jstring, jstring);
// (Ljava/lang/String;Z)V
using nativeRequestVWVisbilityChange = void (JNICALL *)(JNIEnv*, jclass, jstring, jboolean);
// (III)V
using nativeSendResizePanel = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint);
// (III)V
using nativeSendSetPanelAspectRatio = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint);
// (Z)V
using nativeSetBloomIsScrollable = void (JNICALL *)(JNIEnv*, jclass, jboolean);
// (Z)V
using nativeSetQ4bSocialEnabled = void (JNICALL *)(JNIEnv*, jclass, jboolean);
// (Ljava/lang/String;FFLjava/lang/String;Ljava/lang/String;IJ)V
using nativeShowGazeTooltip = void (JNICALL *)(JNIEnv*, jclass, jstring, jfloat, jfloat, jstring, jstring, jint, jlong);
// (IFFFFFFF)V
using nativeSpatializeWindowAtRawPose = void (JNICALL *)(JNIEnv*, jclass, jint, jfloat, jfloat, jfloat, jfloat, jfloat, jfloat, jfloat);
// (Ljava/lang/String;)V
using nativeStopSpatialAudio = void (JNICALL *)(JNIEnv*, jclass, jstring);
// ()V
using nativeSuppressInputs = void (JNICALL *)(JNIEnv*, jclass);
// (I)V
using nativeSystemButtonEvent = void (JNICALL *)(JNIEnv*, jclass, jint);
// (I)V
using nativeSystemDialogRemove = void (JNICALL *)(JNIEnv*, jclass, jint);
// (IIILjava/lang/String;ZZ)V
using nativeSystemDialogShow = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint, jstring, jboolean, jboolean);
// (FFFFLjava/lang/String;)V
using nativeTeleportToCoordinates = void (JNICALL *)(JNIEnv*, jclass, jfloat, jfloat, jfloat, jfloat, jstring);
// (III[I)V
using nativeTextViewResponse = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint, jintArray);
// (I)V
using nativeToastRemove = void (JNICALL *)(JNIEnv*, jclass, jint);
// (IILjava/lang/String;)V
using nativeToastShow = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jstring);
// (Ljava/lang/String;ZZ)V
using nativeTopActivityChanged = void (JNICALL *)(JNIEnv*, jclass, jstring, jboolean, jboolean);
// (Ljava/lang/String;Ljava/lang/String;Z)V
using nativeTravelDownloadComplete = void (JNICALL *)(JNIEnv*, jclass, jstring, jstring, jboolean);
// (ZLjava/lang/String;Ljava/lang/String;ZZLjava/lang/String;)V
using nativeTravelPathwayCommand = void (JNICALL *)(JNIEnv*, jclass, jboolean, jstring, jstring, jboolean, jboolean, jstring);
// (Ljava/lang/String;I)V
using nativeUnanchorWindow = void (JNICALL *)(JNIEnv*, jclass, jstring, jint);
// (III)V
using nativeUpdateAnimatedTTSCursorWithPanelId = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint);
// (I)V
using nativeUpdateCursorType = void (JNICALL *)(JNIEnv*, jclass, jint);
// (Z)V
using nativeUpdateInputVisibility = void (JNICALL *)(JNIEnv*, jclass, jboolean);
// (FI)V
using nativeUpdateMorphCursorScale = void (JNICALL *)(JNIEnv*, jclass, jfloat, jint);
// (IZ)V
using nativeUpdatePanelActiveState = void (JNICALL *)(JNIEnv*, jclass, jint, jboolean);
// (IZ)V
using nativeUpdatePanelPictureInPictureState = void (JNICALL *)(JNIEnv*, jclass, jint, jboolean);
// (IIFF[I)V
using nativeUpdatePointerIcon = void (JNICALL *)(JNIEnv*, jclass, jint, jint, jfloat, jfloat, jintArray);
// (IZ)V
using nativeUpdateWindowDrawnState = void (JNICALL *)(JNIEnv*, jclass, jint, jboolean);
// (Ljava/lang/String;)V
using nativeUpdateWorldMovementSettings = void (JNICALL *)(JNIEnv*, jclass, jstring);
// (Ljava/lang/String;Ljava/lang/String;Z)V
using nativeUserIdentityResponse = void (JNICALL *)(JNIEnv*, jclass, jstring, jstring, jboolean);
// (I)V
using nativeValidateCallbackAppStatus = void (JNICALL *)(JNIEnv*, jclass, jint);
} // namespace metaport::shell::contract
