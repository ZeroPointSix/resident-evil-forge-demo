package com.zeropointsix.redemo.config;

import net.minecraftforge.common.ForgeConfigSpec;

public final class CommonConfig {
    public static final ForgeConfigSpec SPEC;
    public static final ForgeConfigSpec.BooleanValue TYRANT_BREAK_BLOCKS;
    public static final ForgeConfigSpec.DoubleValue DAMAGE_SCALE;
    public static final ForgeConfigSpec.IntValue SOUND_MEMORY_TICKS;
    public static final double LICKER_HEALTH = 120;
    public static final double TYRANT_HEALTH = 400;
    public static final double BIRKIN_HEALTH = 480;
    public static final double EYE_MULTIPLIER = 1.75;
    public static final float LICKER_CLAW_DAMAGE = 10;
    public static final float LICKER_LEAP_DAMAGE = 14;
    public static final float LICKER_TONGUE_DAMAGE = 8;
    public static final float LICKER_AMBUSH_DAMAGE = 14;
    public static final float TYRANT_PUNCH_DAMAGE = 16;
    public static final float TYRANT_SHOVE_DAMAGE = 10;
    public static final float TYRANT_CHARGE_DAMAGE = 22;
    public static final float G1_SLAM_DAMAGE = 14;
    public static final float G1_SWEEP_DAMAGE = 18;
    public static final float G1_GRAB_DAMAGE = 6;
    public static final float G1_GRAB_THROW_DAMAGE = 8;

    static {
        ForgeConfigSpec.Builder b = new ForgeConfigSpec.Builder();
        TYRANT_BREAK_BLOCKS = b.comment("Requires mobGriefing and re_demo:tyrant_breakable; never breaks block entities.")
                .define("tyrantBreakSoftBlocks", true);
        DAMAGE_SCALE = b.comment("Multiplier for this mod's outgoing attack damage.")
                .defineInRange("damageScale", 1.0, 0.1, 5.0);
        SOUND_MEMORY_TICKS = b.comment("Licker forgets a sound-hunt investigation after this many silent ticks. Hurt/combat lock is independent.")
                .defineInRange("lickerSoundMemoryTicks", 120, 40, 600);
        SPEC = b.build();
    }

    private CommonConfig() { }
}
