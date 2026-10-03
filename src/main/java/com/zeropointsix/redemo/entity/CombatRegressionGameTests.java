package com.zeropointsix.redemo.entity;

import com.mojang.authlib.GameProfile;
import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.registry.ModEntities;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.util.Mth;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.damagesource.CombatRules;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.projectile.Arrow;
import net.minecraft.world.entity.projectile.ProjectileUtil;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.util.FakePlayer;
import net.minecraftforge.common.util.FakePlayerFactory;
import net.minecraftforge.gametest.GameTestHolder;
import net.minecraftforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(ResidentEvilMod.MOD_ID)
@PrefixGameTestTemplate(false)
public final class CombatRegressionGameTests {
    private CombatRegressionGameTests() { }

    @GameTest(template = "empty", timeoutTicks = 80)
    public static void deathRemovalWaitsForEachAnimation(GameTestHelper h) {
        EncounterMob[] mobs = {
            h.spawn(ModEntities.LICKER.get(), new BlockPos(3, 2, 4)),
            h.spawn(ModEntities.TYRANT.get(), new BlockPos(7, 2, 4)),
            h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(11, 2, 4))
        };
        int[] expected = {48, 60, 64};
        for (int i = 0; i < mobs.length; i++) {
            EncounterMob mob = mobs[i];
            int duration = expected[i];
            mob.setNoAi(true);
            mob.setNoGravity(true);
            mob.hurt(mob.damageSources().genericKill(), 10000);
            h.assertTrue(!mob.isAlive() && !mob.attacking() && mob.getTarget() == null,
                    "Combat state must clear immediately at death");
            h.runAfterDelay(22, () -> h.assertTrue(!mob.isRemoved(), "Vanilla 20-tick removal must not truncate " + mob.assetId()));
            h.runAfterDelay(duration - 2, () -> h.assertTrue(!mob.isRemoved(), "Full death animation must remain visible: " + mob.assetId()));
            h.runAfterDelay(duration + 2, () -> h.assertTrue(mob.isRemoved() && mob.deathTime == duration,
                    "Removal must happen at the declared animation boundary: " + mob.assetId()));
        }
        h.runAfterDelay(68, h::succeed);
    }

    @GameTest(template = "empty", timeoutTicks = 200)
    public static void tyrantWidensNarrowHoleAndPursuesThroughWall(GameTestHelper h) {
        for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++) {
            h.setBlock(new BlockPos(x, 0, z), Blocks.STONE);
        }
        for (int x = 0; x < 16; x++) for (int y = 1; y <= 4; y++) {
            h.setBlock(new BlockPos(x, y, 6), Blocks.GLASS);
        }
        for (int y = 1; y <= 3; y++) h.setBlock(new BlockPos(7, y, 6), Blocks.AIR);
        var tyrant = h.spawn(ModEntities.TYRANT.get(), new BlockPos(7, 1, 5));
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 1, 12));
        target.setNoAi(true);
        target.setInvulnerable(true);
        tyrant.setTarget(target);
        h.assertTrue(tyrant.hasBreakableAhead(), "Side columns must be found even when the center is air");
        double wallZ = h.absolutePos(new BlockPos(7, 1, 6)).getZ();
        h.runAfterDelay(160, () -> {
            h.assertTrue(tyrant.getZ() > wallZ + 1.6, "Tyrant must physically cross the wall, not only break its center");
            h.assertTrue(h.getLevel().getBlockState(h.absolutePos(new BlockPos(0, 1, 6))).is(Blocks.GLASS), "Breaking must remain bounded near the body");
            h.assertTrue(h.getLevel().getBlockState(h.absolutePos(new BlockPos(7, 0, 6))).is(Blocks.STONE), "Non-whitelisted floor must remain intact");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 55)
    public static void sweepEyeAcceptsRealArrowsAtOpeningAndPeak(GameTestHelper h) {
        G1BirkinEntity[] mobs = sweepFixtures(h);
        h.runAfterDelay(20, () -> shootEyes(h, mobs));
        h.runAfterDelay(23, () -> assertArrowDamage(h, mobs));
        h.runAfterDelay(29, () -> shootEyes(h, mobs));
        h.runAfterDelay(32, () -> {
            assertArrowDamage(h, mobs);
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 55)
    public static void sweepEyeAcceptsPlayerMeleeAtOpeningAndPeak(GameTestHelper h) {
        G1BirkinEntity[] mobs = sweepFixtures(h);
        h.runAfterDelay(20, () -> meleeEyes(h, mobs));
        h.runAfterDelay(29, () -> {
            meleeEyes(h, mobs);
            h.succeed();
        });
    }

    private static G1BirkinEntity[] sweepFixtures(GameTestHelper h) {
        G1BirkinEntity[] mobs = new G1BirkinEntity[4];
        for (int i = 0; i < mobs.length; i++) {
            var mob = h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(4 + (i % 2) * 8, 2, 4 + (i / 2) * 8));
            mob.setNoAi(true);
            mob.setNoGravity(true);
            mob.getAttribute(Attributes.KNOCKBACK_RESISTANCE).setBaseValue(1);
            mob.setYRot(i * 90);
            mob.startAttack(G1BirkinEntity.SWEEP, 40, 20);
            mobs[i] = mob;
        }
        return mobs;
    }

    private static Vec3 front(G1BirkinEntity mob) {
        return new Vec3(0, 0, 1).yRot(-mob.yBodyRot * Mth.DEG_TO_RAD);
    }

    private static void shootEyes(GameTestHelper h, G1BirkinEntity[] mobs) {
        for (G1BirkinEntity mob : mobs) {
            h.assertTrue(mob.isEyeOpen(), "Sweep must expose the eye at ticks 20 and 29");
            h.assertTrue(mob.eyePart().getBoundingBox().getCenter().distanceTo(mob.eyeCenter()) < 0.001,
                    "Part must match stable visible-eye coordinates for every body yaw");
            mob.invulnerableTime = 0;
            mob.setHealth(mob.getMaxHealth());
            Vec3 direction = front(mob);
            Vec3 start = mob.eyeCenter().add(direction.scale(3));
            Arrow arrow = new Arrow(h.getLevel(), start.x, start.y, start.z);
            arrow.setNoGravity(true);
            arrow.setBaseDamage(2);
            arrow.setDeltaMovement(direction.scale(-3));
            h.getLevel().addFreshEntity(arrow);
        }
    }

    private static void assertArrowDamage(GameTestHelper h, G1BirkinEntity[] mobs) {
        float expected = CombatRules.getDamageAfterAbsorb(6, 8, 0) * 1.75F;
        for (G1BirkinEntity mob : mobs) {
            h.assertTrue(Math.abs(mob.getMaxHealth() - mob.getHealth() - expected) < 0.01,
                    "Moving vanilla arrow must produce weak-point damage, yaw=" + mob.yBodyRot + " actual=" + (mob.getMaxHealth() - mob.getHealth()));
        }
    }

    private static void meleeEyes(GameTestHelper h, G1BirkinEntity[] mobs) {
        FakePlayer player = FakePlayerFactory.get(h.getLevel(), new GameProfile(UUID.fromString("df13d884-df39-4b1c-9ca9-c1c5aadbe109"), "WeakPointQA"));
        Vec3 oldPosition = player.position();
        float oldYaw = player.getYRot(), oldPitch = player.getXRot(), oldHeadYaw = player.getYHeadRot();
        ItemStack oldHand = player.getMainHandItem().copy();
        double oldDamage = player.getAttribute(Attributes.ATTACK_DAMAGE).getBaseValue();
        double oldSpeed = player.getAttribute(Attributes.ATTACK_SPEED).getBaseValue();
        try {
            player.setItemInHand(InteractionHand.MAIN_HAND, ItemStack.EMPTY);
            player.getAttribute(Attributes.ATTACK_DAMAGE).setBaseValue(8);
            player.getAttribute(Attributes.ATTACK_SPEED).setBaseValue(1024);
            for (G1BirkinEntity mob : mobs) {
                h.assertTrue(mob.isEyeOpen(), "Sweep eye must be open for melee");
                mob.invulnerableTime = 0;
                mob.setHealth(mob.getMaxHealth());
                Vec3 start = mob.eyeCenter().add(front(mob).scale(2.5));
                player.setPos(start.subtract(0, player.getEyeHeight(), 0));
                player.setYRot(mob.yBodyRot + 180);
                player.setYHeadRot(mob.yBodyRot + 180);
                player.setXRot(0);
                Vec3 end = start.add(player.getViewVector(1).scale(3));
                var hit = ProjectileUtil.getEntityHitResult(h.getLevel(), player, start, end, new AABB(start, end).inflate(1),
                        entity -> entity.isPickable() && !entity.isSpectator());
                h.assertTrue(hit != null && (hit.getEntity() == mob || hit.getEntity() == mob.eyePart()),
                        "Player aim must select the real boss or its eye: yaw=" + mob.yBodyRot + " view=" + player.getViewVector(1) + " hit=" + (hit == null ? "none" : hit.getEntity()));
                player.attack(hit.getEntity());
                float expected = CombatRules.getDamageAfterAbsorb(8, 8, 0) * 1.75F;
                h.assertTrue(Math.abs(mob.getMaxHealth() - mob.getHealth() - expected) < 0.01,
                        "Player.attack must produce weak-point damage, yaw=" + mob.yBodyRot);
            }
        } finally {
            player.setPos(oldPosition);
            player.setYRot(oldYaw);
            player.setYHeadRot(oldHeadYaw);
            player.setXRot(oldPitch);
            player.setItemInHand(InteractionHand.MAIN_HAND, oldHand);
            player.getAttribute(Attributes.ATTACK_DAMAGE).setBaseValue(oldDamage);
            player.getAttribute(Attributes.ATTACK_SPEED).setBaseValue(oldSpeed);
        }
    }
}
