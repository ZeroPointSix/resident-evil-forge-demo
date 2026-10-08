package com.zeropointsix.redemo.entity;

import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.entity.ai.SoundInvestigateGoal;
import com.zeropointsix.redemo.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.block.Blocks;
import net.minecraftforge.gametest.GameTestHolder;
import net.minecraftforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(ResidentEvilMod.MOD_ID)
@PrefixGameTestTemplate(false)
public final class CombatPressureGameTests {
    private CombatPressureGameTests() { }

    @GameTest(template = "empty", timeoutTicks = 20)
    public static void openArenaColumnRemovesOverheadFluidBeforeCombat(GameTestHelper h) {
        BlockPos floor = h.absolutePos(new BlockPos(4, 1, 4));
        BlockPos overhead = floor.above(20);
        BlockPos neighbor = overhead.east();
        var level = h.getLevel();
        level.setBlock(overhead, Blocks.LAVA.defaultBlockState(), 2);
        level.setBlock(overhead.above(), Blocks.STONE.defaultBlockState(), 2);
        level.setBlock(neighbor, Blocks.GLASS.defaultBlockState(), 2);
        try {
            CombatBalanceGameTests.prepareOpenColumn(level, floor);
            h.assertTrue(level.getBlockState(floor).is(Blocks.STONE), "Arena keeps its solid floor");
            h.assertTrue(level.getBlockState(overhead).isAir() && level.getBlockState(overhead.above()).isAir(),
                    "A generated lava source and roof above template height must be cleared before combat");
            h.assertTrue(level.getBlockState(neighbor).is(Blocks.GLASS), "Column preparation must not modify its neighbor");
            h.succeed();
        } finally {
            level.setBlock(overhead, Blocks.AIR.defaultBlockState(), 2);
            level.setBlock(overhead.above(), Blocks.AIR.defaultBlockState(), 2);
            level.setBlock(neighbor, Blocks.AIR.defaultBlockState(), 2);
        }
    }

    @GameTest(template = "empty", timeoutTicks = 30)
    public static void clawEngagesAtVictimEdgeWithoutExtendingContact(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(4, 2, 4));
        var golem = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 2, 7));
        licker.setNoAi(true);
        licker.setNoGravity(true);
        golem.setNoAi(true);
        golem.setNoGravity(true);
        golem.getAttribute(Attributes.KNOCKBACK_RESISTANCE).setBaseValue(1);
        licker.setTarget(golem);
        double reach = CommonConfig.LICKER_CLAW_RANGE + golem.getBbWidth() * 0.5;
        for (double height : new double[]{2.6, 2.8}) {
            golem.setPos(licker.getX(), licker.getY() + height, licker.getZ());
            h.assertTrue(!licker.inClawRange(golem), "Out-of-height victims must not suppress climbing: " + height);
        }
        golem.setPos(licker.getX(), licker.getY(), licker.getZ() + reach + 0.1);
        h.assertTrue(!licker.inClawRange(golem), "Targets beyond the unchanged claw reach must not trigger it");
        golem.setPos(licker.getX(), licker.getY(), licker.getZ() + reach - 0.1);
        h.assertTrue(licker.inClawRange(golem), "A wide victim already touching claw reach must not create an idle ring");
        for (int y = 1; y <= 4; y++) h.setBlock(new BlockPos(4, y, 5), Blocks.STONE);
        h.assertTrue(!licker.inClawRange(golem), "A victim behind a solid wall is not a claw target");
        for (int y = 1; y <= 4; y++) h.setBlock(new BlockPos(4, y, 5), Blocks.AIR);
        licker.startAttack(LickerEntity.CLAW, 20, CommonConfig.LICKER_RECOVERY, CommonConfig.LICKER_ATTACK_SPEED);
        int impact = licker.attackFrameAt(9);
        h.runAfterDelay(impact - 1, () -> h.assertTrue(golem.getHealth() == 100, "Edge contact keeps its visible windup"));
        h.runAfterDelay(impact + 2, () -> {
            h.assertTrue(golem.getHealth() == 90, "Existing contact range must land exactly one normal claw hit");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 30)
    public static void soundPursuitResumesAtEveryTickPhase(GameTestHelper h) {
        for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++) h.setBlock(new BlockPos(x, 0, z), Blocks.STONE);
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(5, 1, 3));
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(5, 1, 10));
        licker.setNoAi(true);
        target.setNoAi(true);
        // This test drives only the goal lifecycle, before the first physics tick.
        licker.setOnGround(true);
        licker.setTarget(target);
        var goal = new SoundInvestigateGoal(licker);
        h.assertTrue(goal.requiresUpdateEveryTick(), "Pursuit must not depend on alternate goal ticks");
        for (int phase = 0; phase < 10; phase++) {
            licker.tickCount = phase;
            goal.stop();
            goal.start();
            h.assertTrue(!licker.getNavigation().isDone(), "Attack recovery must resume navigation immediately at phase " + phase);
        }
        goal.stop();
        licker.startAttack(LickerEntity.CLAW, 20, 2, 1.8);
        goal.start();
        goal.tick();
        h.assertTrue(licker.getNavigation().isDone(), "An alternate goal tick must not restart navigation during an attack");
        h.assertTrue(licker.attackFrameAt(9) == 5, "Exact model contact must not be delayed by float replication");
        h.assertTrue(licker.attackFrameAt(20) == 12, "Fractional end frames must still round upward");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void acceleratedTongueHitsAtContactAndPullsOnce(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(4, 2, 4));
        var golem = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 2, 7));
        licker.setNoAi(true);
        licker.setNoGravity(true);
        golem.setNoAi(true);
        golem.setNoGravity(true);
        licker.setTarget(golem);
        licker.startAttack(LickerEntity.TONGUE, 24, CommonConfig.LICKER_TONGUE_RECOVERY, CommonConfig.LICKER_ATTACK_SPEED);
        int impact = licker.attackFrameAt(CommonConfig.LICKER_TONGUE_HIT_FRAME);
        h.runAfterDelay(impact - 1, () -> h.assertTrue(golem.getHealth() == 100, "Tongue telegraph must not deal early damage"));
        h.runAfterDelay(impact + 1, () -> {
            h.assertTrue(golem.getHealth() == 92, "Tongue contact must land its configured damage exactly once");
            h.assertTrue(golem.getDeltaMovement().z < 0, "A landed tongue must pull toward the Licker");
        });
        h.runAfterDelay(22, () -> {
            h.assertTrue(golem.getHealth() == 92 && !licker.attacking(), "Tongue recovery cannot repeat the hit");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 20)
    public static void tongueTracksDuringWindupButLocksAtContact(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(4, 2, 4));
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 2, 7));
        licker.setNoAi(true);
        licker.setNoGravity(true);
        target.setNoAi(true);
        target.setNoGravity(true);
        licker.setTarget(target);
        licker.startAttack(LickerEntity.TONGUE, 24, CommonConfig.LICKER_TONGUE_RECOVERY, CommonConfig.LICKER_ATTACK_SPEED);
        h.assertTrue(licker.cooldown == licker.attackFrameAt(24) + 1,
                "Tongue recovery is one tick after its complete animation, not a truncated clip");
        target.setPos(licker.getX() + 3, licker.getY(), licker.getZ());
        licker.attackFrame(LickerEntity.TONGUE, 1);
        h.assertTrue(Math.abs(licker.attackYaw + 20) < 0.01, "Tongue turns at the bounded 20 degrees per windup tick");
        h.assertTrue(target.getHealth() == 100, "Tracking during windup cannot inflict early damage");
        licker.attackFrame(LickerEntity.TONGUE, licker.attackFrameAt(CommonConfig.LICKER_TONGUE_HIT_FRAME));
        h.assertTrue(Math.abs(licker.attackYaw + 20) < 0.01 && target.getHealth() == 100,
                "Contact cannot snap to a target that has moved outside the telegraphed cone");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 20)
    public static void tongueCatchesSidestepWithoutBecomingWideSweep(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(6, 2, 4));
        var sidestep = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 2, 7));
        var outside = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 2, 7));
        for (var actor : new net.minecraft.world.entity.Mob[] {licker, sidestep, outside}) {
            actor.setNoAi(true);
            actor.setNoGravity(true);
        }
        sidestep.setPos(licker.getX() + Math.sin(Math.toRadians(21)) * 3,
                licker.getY(), licker.getZ() + Math.cos(Math.toRadians(21)) * 3);
        outside.setPos(licker.getX() - Math.sin(Math.toRadians(35)) * 3,
                licker.getY(), licker.getZ() + Math.cos(Math.toRadians(35)) * 3);
        outside.setTarget(licker);
        licker.setTarget(sidestep);
        licker.startAttack(LickerEntity.TONGUE, 24, CommonConfig.LICKER_TONGUE_RECOVERY, CommonConfig.LICKER_ATTACK_SPEED);
        // Simulate a sidestep after the final windup tracking tick.
        licker.attackYaw = 0;
        int impact = licker.attackFrameAt(CommonConfig.LICKER_TONGUE_HIT_FRAME);
        licker.attackFrame(LickerEntity.TONGUE, impact);
        h.assertTrue(sidestep.getHealth() == 92, "A small final-tick sidestep still takes the unchanged tongue hit");
        h.assertTrue(outside.getHealth() == 100, "Tongue must not become a broad cleave");
        h.assertTrue(licker.attackHits.size() == 1, "Only the victim in the narrow contact cone is hit");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 50)
    public static void acceleratedClawKeepsTelegraphAndSingleHit(GameTestHelper h) {
        var licker = h.spawn(ModEntities.LICKER.get(), new BlockPos(4, 2, 4));
        var golem = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 2, 6));
        licker.setNoAi(true);
        licker.setNoGravity(true);
        golem.setNoAi(true);
        golem.setNoGravity(true);
        golem.getAttribute(Attributes.KNOCKBACK_RESISTANCE).setBaseValue(1);
        licker.setTarget(golem);
        licker.startAttack(LickerEntity.CLAW, 20, 2, CommonConfig.LICKER_ATTACK_SPEED);
        int impact = licker.attackFrameAt(9);
        h.runAfterDelay(impact - 1, () -> h.assertTrue(golem.getHealth() == 100, "No damage before animation contact"));
        h.runAfterDelay(impact + 2, () -> h.assertTrue(golem.getHealth() == 90, "Contact produces exactly one claw hit"));
        h.runAfterDelay(18, () -> {
            h.assertTrue(golem.getHealth() == 90 && !licker.attacking(), "Recovery never repeats damage");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 30)
    public static void sweepHitsOtherAttackersButNotBystanders(GameTestHelper h) {
        var tyrant = h.spawn(ModEntities.TYRANT.get(), new BlockPos(7, 2, 4));
        tyrant.setNoAi(true);
        tyrant.setNoGravity(true);
        var first = h.spawn(EntityType.IRON_GOLEM, new BlockPos(6, 2, 6));
        var second = h.spawn(EntityType.IRON_GOLEM, new BlockPos(8, 2, 6));
        var third = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 2, 6));
        var bystander = h.spawn(EntityType.COW, new BlockPos(7, 2, 7));
        for (var victim : new net.minecraft.world.entity.Mob[] {first, second, third, bystander}) {
            victim.setNoAi(true);
            victim.setNoGravity(true);
        }
        first.setTarget(tyrant);
        second.setTarget(tyrant);
        third.setTarget(tyrant);
        tyrant.setTarget(first);
        tyrant.attackYaw = 0;
        tyrant.strike(4, 160, 10, 0);
        tyrant.strike(4, 160, 10, 0);
        h.assertTrue(first.getHealth() == 90 && second.getHealth() == 90 && third.getHealth() == 90,
                "Tyrant retains broad pressure: all three hostiles in the arc get one hit");
        h.assertTrue(bystander.getHealth() == bystander.getMaxHealth(), "Unrelated passive mobs are not collateral targets");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void birkinCleavePrioritizesTargetAndResetsBudget(GameTestHelper h) {
        var birkin = h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(7, 2, 4));
        birkin.setNoAi(true);
        birkin.setNoGravity(true);
        var near = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 2, 6));
        var middle = h.spawn(EntityType.IRON_GOLEM, new BlockPos(8, 2, 6));
        var far = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 2, 7));
        var golems = new net.minecraft.world.entity.animal.IronGolem[] {near, middle, far};
        for (var golem : golems) {
            golem.setNoAi(true);
            golem.setNoGravity(true);
            golem.setTarget(birkin);
        }
        birkin.setTarget(far);
        birkin.startAttack(G1BirkinEntity.SWEEP, 1, 1);
        birkin.strike(4, 160, 18, 0);
        h.assertTrue(far.getHealth() == 82 && near.getHealth() == 82 && middle.getHealth() == 100,
                "The locked target takes priority over a nearer secondary opponent");
        h.runAfterDelay(3, () -> {
            for (var golem : golems) {
                golem.setHealth(100);
                golem.invulnerableTime = 0;
            }
            birkin.setTarget(middle);
            birkin.startAttack(G1BirkinEntity.SWEEP, 40, 6);
            birkin.strike(4, 160, 18, 0);
            h.assertTrue(birkin.attackSequence() == 2 && middle.getHealth() == 82
                            && near.getHealth() == 82 && far.getHealth() == 100,
                    "A new attack sequence must reset its two-target hit budget");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void birkinCleaveBudgetCountsSuccessfulTargetsAcrossFrames(GameTestHelper h) {
        var birkin = h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(7, 2, 4));
        birkin.setNoAi(true);
        birkin.setNoGravity(true);
        var near = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 2, 6));
        var middle = h.spawn(EntityType.IRON_GOLEM, new BlockPos(8, 2, 6));
        var primary = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 2, 7));
        for (var golem : new net.minecraft.world.entity.animal.IronGolem[] {near, middle, primary}) {
            golem.setNoAi(true);
            golem.setNoGravity(true);
            golem.setTarget(birkin);
        }
        near.setInvulnerable(true);
        birkin.setTarget(primary);
        birkin.startAttack(G1BirkinEntity.SWEEP, 40, 6);
        birkin.strike(4, 160, 18, 0);
        h.assertTrue(primary.getHealth() == 82 && middle.getHealth() == 82 && near.getHealth() == 100,
                "Primary and nearest damageable opponent get the two successful-hit slots");
        near.setInvulnerable(false);
        birkin.strike(4, 160, 18, 0);
        h.assertTrue(near.getHealth() == 100 && primary.getHealth() == 82 && middle.getHealth() == 82,
                "Later strike frames must not acquire a third victim or repeat the first two hits");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 40)
    public static void softBreakingRequiresPursuitAndPreservesFloor(GameTestHelper h) {
        var tyrant = h.spawn(ModEntities.TYRANT.get(), new BlockPos(7, 1, 4));
        tyrant.setNoAi(true);
        tyrant.attackYaw = 0;
        var level = h.getLevel();
        boolean previous = level.getGameRules().getBoolean(GameRules.RULE_MOBGRIEFING);
        try {
            level.getGameRules().getRule(GameRules.RULE_MOBGRIEFING).set(true, level.getServer());
            for (int x = 5; x <= 9; x++) for (int y = 1; y <= 3; y++) h.setBlock(new BlockPos(x, y, 5), Blocks.OAK_PLANKS);
            h.setBlock(new BlockPos(7, 0, 5), Blocks.DIRT);
            h.setBlock(new BlockPos(7, 1, 6), Blocks.OAK_LOG);
            tyrant.breakSoftObstacles();
            h.assertTrue(level.getBlockState(h.absolutePos(new BlockPos(7, 1, 5))).is(Blocks.OAK_PLANKS), "Idle mob must not demolish terrain");
            var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 1, 10));
            target.setNoAi(true);
            tyrant.setTarget(target);
            tyrant.breakSoftObstacles();
            int removed = 0;
            for (int x = 5; x <= 9; x++) for (int y = 1; y <= 3; y++) {
                if (level.getBlockState(h.absolutePos(new BlockPos(x, y, 5))).isAir()) removed++;
            }
            h.assertTrue(removed > 0 && removed <= CommonConfig.TYRANT_BREAK_LIMIT, "One break has a hard block budget");
            h.assertTrue(level.getBlockState(h.absolutePos(new BlockPos(7, 0, 5))).is(Blocks.DIRT), "Whitelisted floor stays intact");
            h.assertTrue(level.getBlockState(h.absolutePos(new BlockPos(7, 1, 6))).is(Blocks.OAK_LOG), "No recursive spread into the next layer");
            h.assertTrue(Blocks.OAK_LEAVES.defaultBlockState().is(TyrantEntity.BREAKABLE)
                    && Blocks.OAK_LOG.defaultBlockState().is(TyrantEntity.BREAKABLE)
                    && Blocks.DIRT.defaultBlockState().is(TyrantEntity.BREAKABLE)
                    && Blocks.GLASS.defaultBlockState().is(TyrantEntity.BREAKABLE), "Soft material families are tagged");
            h.succeed();
        } finally {
            level.getGameRules().getRule(GameRules.RULE_MOBGRIEFING).set(previous, level.getServer());
        }
    }

    @GameTest(template = "empty", timeoutTicks = 70)
    public static void birkinLungeClosesGapWithRealCollision(GameTestHelper h) {
        for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++) h.setBlock(new BlockPos(x, 0, z), Blocks.STONE);
        var birkin = h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(7, 1, 3));
        var golem = h.spawn(EntityType.IRON_GOLEM, new BlockPos(7, 1, 9));
        golem.setNoAi(true);
        golem.getAttribute(Attributes.KNOCKBACK_RESISTANCE).setBaseValue(1);
        birkin.setTarget(golem);
        double initial = birkin.distanceTo(golem);
        boolean[] lunged = {false};
        h.succeedWhen(() -> {
            if (birkin.attack() == G1BirkinEntity.LUNGE) lunged[0] = true;
            h.assertTrue(lunged[0] && birkin.distanceTo(golem) < initial - 2, "Short lunge must visibly cover ground");
        });
    }

    @GameTest(template = "empty", timeoutTicks = 45)
    public static void birkinWindupReleasesExposurePose(GameTestHelper h) {
        var birkin = h.spawn(ModEntities.G1_BIRKIN.get(), new BlockPos(7, 2, 3));
        birkin.setNoAi(true);
        birkin.setNoGravity(true);
        birkin.openWeakPoint(70);
        birkin.startAttack(G1BirkinEntity.SLAM, 36, 6, CommonConfig.G1_ATTACK_SPEED);
        birkin.setHealth(birkin.getMaxHealth() * 0.25F);
        birkin.updatePhase();
        h.assertTrue(!birkin.isBerserk(), "Phase changes wait for the current attack to finish");
        h.assertTrue(!birkin.isEyeOpen(), "New attack must release the fixed exposure pose for its windup");
        h.runAfterDelay(birkin.attackFrameAt(18) + 2, () -> {
            h.assertTrue(birkin.isEyeOpen(), "Impact must restore the visible and damageable shoulder weakness");
            h.succeed();
        });
    }
}
