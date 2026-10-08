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
    public static final double MELEE_MAX_Y_DIFFERENCE = 2.5;
    public static final double MELEE_VERTICAL_SEARCH = 1.5;
    public static final double LICKER_ATTACK_SPEED = 1.90;
    public static final int LICKER_RECOVERY = 3;
    public static final int LICKER_TONGUE_RECOVERY = 1;
    public static final int LICKER_TONGUE_COOLDOWN = 21;
    public static final double LICKER_CLAW_RANGE = 2.3;
    public static final int LICKER_LEAP_COOLDOWN = 65;
    public static final int LICKER_TONGUE_HIT_FRAME = 9;
    public static final double LICKER_TONGUE_RANGE = 4.2;
    public static final double LICKER_TONGUE_ARC = 46;
    public static final float LICKER_TONGUE_TRACKING = 20;
    public static final double LICKER_TONGUE_PULL = 0.50;
    public static final double LICKER_PRESSURE_STEP = 0.12;
    public static final double LICKER_KNOCKBACK_RESISTANCE = 0.45;
    public static final double LICKER_MOVE_SPEED = 0.32;
    public static final int LICKER_REPATH_TICKS = 4;
    public static final double LICKER_PURSUIT_SPEED = 1.2;
    public static final double LICKER_INVESTIGATION_SPEED = 0.8;
    public static final double TYRANT_ATTACK_SPEED = 2.00;
    public static final double TYRANT_RAGE_ATTACK_SPEED = 2.4;
    public static final double TYRANT_TRANSITION_SPEED = 2.0;
    public static final int TYRANT_RECOVERY = 1;
    public static final int TYRANT_CHARGE_COOLDOWN = 90;
    public static final int TYRANT_BREAK_COOLDOWN = 30;
    public static final int TYRANT_BREAK_LIMIT = 6;
    public static final double TYRANT_MAX_BREAK_HARDNESS = 3;
    public static final double TYRANT_MOVE_SPEED = 0.24;
    public static final double TYRANT_PRESSURE_STEP = 0.22;
    public static final double G1_ATTACK_SPEED = 1.35;
    public static final double G1_BERSERK_ATTACK_SPEED = 1.75;
    public static final double G1_GRAB_MAX_SPEED = 1.5;
    public static final int G1_RECOVERY = 12;
    public static final int G1_BERSERK_RECOVERY = 6;
    public static final int G1_MAX_ATTACK_TARGETS = 2;
    public static final double G1_KNOCKBACK_RESISTANCE = 0.45;
    public static final double G1_SLAM_RANGE = 3.3;
    public static final double G1_SLAM_ARC = 80;
    public static final double G1_SWEEP_RANGE = 3.4;
    public static final double G1_SWEEP_ARC = 80;
    public static final int G1_LUNGE_COOLDOWN = 55;
    public static final int G1_BERSERK_LUNGE_COOLDOWN = 35;
    public static final double G1_LUNGE_SPEED = 0.52;
    public static final double G1_LUNGE_RANGE = 6.5;
    public static final int G1_EYE_WINDOW = 24;
    public static final int G1_BERSERK_EYE_WINDOW = 70;

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
