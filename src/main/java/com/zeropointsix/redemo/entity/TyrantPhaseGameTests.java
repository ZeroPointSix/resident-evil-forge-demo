package com.zeropointsix.redemo.entity;

import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.config.CommonConfig;
import com.zeropointsix.redemo.registry.ModEntities;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.block.Blocks;
import net.minecraftforge.gametest.GameTestHolder;
import net.minecraftforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(ResidentEvilMod.MOD_ID)
@PrefixGameTestTemplate(false)
public final class TyrantPhaseGameTests {
    private TyrantPhaseGameTests() { }

    private static TyrantEntity tyrant(GameTestHelper h) {
        var mob = h.spawn(ModEntities.TYRANT.get(), new BlockPos(4, 2, 3));
        mob.setNoAi(true);
        mob.setNoGravity(true);
        return mob;
    }

    private static List<TyrantDebrisEntity> debris(GameTestHelper h, TyrantEntity owner) {
        return h.getLevel().getEntitiesOfClass(TyrantDebrisEntity.class, owner.getBoundingBox().inflate(40),
                rock -> rock.getOwner() == owner);
    }

    @GameTest(template = "empty", timeoutTicks = 20)
    public static void exactThresholdPersistsWithoutStackingModifiers(GameTestHelper h) {
        var mob = tyrant(h);
        h.assertTrue(Math.abs(mob.getBbHeight() - 4) < .001, "Tyrant collision height is four blocks");
        mob.setHealth(121);
        mob.updatePhase();
        h.assertTrue(!mob.isRaging() && mob.canThrowDebris(), "Above 30 percent keeps coat and ranged attacks");
        mob.setHealth(120);
        mob.updatePhase();
        h.assertTrue(mob.isRaging() && mob.attack() == TyrantEntity.RAGE && !mob.canThrowDebris(), "Exactly 30 percent enters rage once");
        h.assertTrue(mob.getArmorValue() == 4, "Losing the limiter coat reduces armor from twelve to four");
        h.assertTrue(Math.abs(mob.getAttributeValue(Attributes.MOVEMENT_SPEED) - .4) < .001, "Rage raises pursuit speed");
        mob.setHealth(200);
        CompoundTag saved = new CompoundTag();
        mob.addAdditionalSaveData(saved);
        var restored = ModEntities.TYRANT.get().create(h.getLevel());
        restored.readAdditionalSaveData(saved);
        restored.readAdditionalSaveData(saved);
        h.assertTrue(restored.isRaging() && !restored.canThrowDebris() && restored.getArmorValue() == 4,
                "Reload and healing do not restore the coat, ranged attacks or stack modifiers");
        h.assertTrue(Math.abs(restored.getAttributeValue(Attributes.MOVEMENT_SPEED) - .4) < .001, "Reload keeps one speed modifier");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 20)
    public static void meleeAlternatesAndEyeIsARealWeakPoint(GameTestHelper h) {
        var mob = tyrant(h);
        for (int expected : new int[] {TyrantEntity.PUNCH, TyrantEntity.PUNCH_LEFT, TyrantEntity.SHOVE, TyrantEntity.SHOVE_LEFT})
            h.assertTrue(mob.nextMeleeAttack() == expected, "Normal attacks cycle distinct left and right clips");
        h.assertTrue(!mob.eyePart().isPickable(), "Coated eye cannot be targeted");
        mob.setHealth(120);
        mob.updatePhase();
        h.assertTrue(mob.nextMeleeAttack() == TyrantEntity.SLASH && mob.nextMeleeAttack() == TyrantEntity.SLASH_LEFT,
                "Rage uses alternating blade attacks");
        var source = h.getLevel().damageSources().generic();
        mob.invulnerableTime = 0;
        float before = mob.getHealth();
        mob.hurt(source, 8);
        float normal = before - mob.getHealth();
        mob.invulnerableTime = 0;
        before = mob.getHealth();
        h.assertTrue(mob.eyePart().hurt(source, 8), "Eye part accepts a real server hit");
        float weak = before - mob.getHealth();
        h.assertTrue(Math.abs(weak - normal * CommonConfig.TYRANT_EYE_MULTIPLIER) < .001,
                "Eye multiplies damage after armor without changing body damage");
        h.succeed();
    }

    @GameTest(template = "empty", timeoutTicks = 80)
    public static void debrisHasTelegraphCollisionAndCannotLaunchAtLowHealth(GameTestHelper h) {
        var mob = tyrant(h);
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 2, 12));
        target.setNoAi(true);
        target.setNoGravity(true);
        mob.setTarget(target);
        mob.startAttack(TyrantEntity.THROW, 36, 8, 1.25);
        int launch = mob.attackFrameAt(20);
        h.runAfterDelay(launch - 1, () -> h.assertTrue(debris(h, mob).isEmpty(), "Throw cannot spawn before visible release"));
        h.runAfterDelay(launch + 1, () -> {
            var rocks = debris(h, mob);
            h.assertTrue(rocks.size() == 3, "The release creates three real moving stone projectiles");
            h.assertTrue(rocks.stream().allMatch(rock -> rock.getDeltaMovement().length() > 1), "Debris has real travel velocity");
        });
        h.runAfterDelay(launch + 3, () -> h.assertTrue(debris(h, mob).stream().anyMatch(
                rock -> rock.getZ() > mob.getZ() + 2 && rock.getDeltaMovement().y < 0),
                "Rocks travel forward and descend toward the lower target under gravity"));
        h.runAfterDelay(40, () -> {
            h.assertTrue(target.getHealth() < 100, "A ranged target must take a real projectile hit");
            debris(h, mob).forEach(entity -> entity.discard());
            mob.setHealth(120);
            mob.throwDebris();
            h.assertTrue(debris(h, mob).isEmpty(),
                    "Health threshold blocks throw immediately, even before phase transition finishes");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 70)
    public static void debrisStopsAtWallsAndNeverEditsTerrain(GameTestHelper h) {
        var mob = tyrant(h);
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 2, 12));
        target.setNoAi(true);
        target.setNoGravity(true);
        mob.setTarget(target);
        mob.attackYaw = 0;
        mob.throwDebris();
        for (int x = 2; x <= 6; x++) for (int y = 1; y <= 8; y++) h.setBlock(new BlockPos(x, y, 6), Blocks.STONE);
        h.runAfterDelay(45, () -> {
            h.assertTrue(target.getHealth() == 100, "Stone projectiles cannot pass through a wall");
            h.assertTrue(h.getBlockState(new BlockPos(4, 4, 6)).is(Blocks.STONE), "Projectile impacts never destroy terrain");
            h.assertTrue(debris(h, mob).isEmpty(),
                    "Collided debris must be discarded");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 50)
    public static void chargeActuallyMovesAndHitsOnce(GameTestHelper h) {
        var mob = tyrant(h);
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 2, 9));
        target.setNoAi(true);
        target.setNoGravity(true);
        mob.setTarget(target);
        double startZ = mob.getZ();
        mob.startAttack(TyrantEntity.CHARGE, 40, 1, CommonConfig.TYRANT_ATTACK_SPEED);
        h.runAfterDelay(9, () -> h.assertTrue(target.getHealth() == 100, "Charge windup cannot deal early damage"));
        h.runAfterDelay(25, () -> {
            h.assertTrue(mob.getZ() > startZ + 3, "Charge moves the real collision body at least three blocks");
            h.assertTrue(Math.abs(target.getHealth() - 78) < .001, "Charge deals one real twenty-two damage contact hit");
            h.succeed();
        });
    }

    @GameTest(template = "empty", timeoutTicks = 50)
    public static void slashKeepsContactFrameAndSingleHitBudget(GameTestHelper h) {
        var mob = tyrant(h);
        var target = h.spawn(EntityType.IRON_GOLEM, new BlockPos(4, 2, 5));
        target.setNoAi(true);
        target.setNoGravity(true);
        mob.setTarget(target);
        mob.setHealth(120);
        mob.updatePhase();
        h.runAfterDelay(24, () -> {
            mob.startAttack(TyrantEntity.SLASH, 24, 1, CommonConfig.TYRANT_RAGE_ATTACK_SPEED);
            mob.attackYaw = 0;
            h.assertTrue(mob.attack() == TyrantEntity.SLASH && mob.animationSpeed() == 3,
                    "The real slash state runs faster than the normal attack rate of two");
            float health = target.getHealth();
            int frame = mob.attackFrameAt(10);
            mob.attackFrame(TyrantEntity.SLASH, frame - 1);
            h.assertTrue(target.getHealth() == health, "Blade windup does not deal early damage");
            mob.attackFrame(TyrantEntity.SLASH, frame);
            h.assertTrue(Math.abs(target.getHealth() - (health - 25.6F)) < .001, "Blade impact uses the rage damage multiplier");
            target.invulnerableTime = 0;
            mob.attackFrame(TyrantEntity.SLASH, frame);
            h.assertTrue(Math.abs(target.getHealth() - (health - 25.6F)) < .001, "One swing cannot damage a victim twice");
            h.succeed();
        });
    }
}
