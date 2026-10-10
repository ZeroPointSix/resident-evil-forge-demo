package com.zeropointsix.redemo.client;

import com.zeropointsix.redemo.ResidentEvilMod;
import com.zeropointsix.redemo.entity.EncounterMob;
import com.zeropointsix.redemo.entity.G1BirkinEntity;
import com.zeropointsix.redemo.entity.LickerEntity;
import com.zeropointsix.redemo.entity.TyrantEntity;
import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.model.GeoModel;

public final class CreatureModel<T extends EncounterMob> extends GeoModel<T> {
    private final String id;

    public CreatureModel(String id) { this.id = id; }

    @Override
    public ResourceLocation getModelResource(T entity) { return new ResourceLocation(ResidentEvilMod.MOD_ID, "geo/" + id + ".geo.json"); }

    @Override
    public ResourceLocation getTextureResource(T entity) { return new ResourceLocation(ResidentEvilMod.MOD_ID, "textures/entity/" + id + ".png"); }

    @Override
    public ResourceLocation getAnimationResource(T entity) { return new ResourceLocation(ResidentEvilMod.MOD_ID, "animations/" + id + ".animation.json"); }

    @Override
    public void setCustomAnimations(T entity, long instanceId, AnimationState<T> state) {
        super.setCustomAnimations(entity, instanceId, state);
        if (entity instanceof TyrantEntity tyrant) {
            hide("coat_intact", tyrant.isRaging());
            hide("coat_torn", !tyrant.isRaging());
            hide("tyrant_eye", !tyrant.isRaging());
            for (String name : new String[] { "part_coat_chest", "part_back_storm_panel", "part_lapel_-1", "part_lapel_1",
                    "part_high_collar_-1", "part_high_collar_1", "part_shoulder_yoke_-1", "part_shoulder_yoke_1",
                    "part_upper_sleeve_-1", "part_upper_sleeve_1", "part_fore_sleeve_-1", "part_fore_sleeve_1",
                    "part_cuff_-1", "part_cuff_1" }) hide(name, tyrant.isRaging());
            for (String name : new String[] { "mutant_chest", "mutant_shoulder", "mutant_upper_r", "mutant_upper_l",
                    "mutant_forearm_r", "mutant_forearm_l", "blade_r", "blade_l" }) hide(name, !tyrant.isRaging());
            if (tyrant.isAlive() && tyrant.isRaging()) {
                for (String name : TyrantEntity.EXPOSURE_BONES) {
                    var bone = getAnimationProcessor().getBone(name);
                    if (bone == null) continue;
                    bone.setRotX(0);
                    bone.setRotY(0);
                    bone.setRotZ(0);
                    bone.setPosX(0);
                    bone.setPosY(0);
                    bone.setPosZ(0);
                    bone.setScaleX(1);
                    bone.setScaleY(1);
                    bone.setScaleZ(1);
                }
            }
        }
        if (entity instanceof G1BirkinEntity birkin) {
            hide("eye_open", !birkin.isEyeOpen());
            hide("eye_closed", birkin.isEyeOpen());
            if (birkin.isAlive() && birkin.isEyeOpen()) {
                // The exposure pose is a gameplay contract shared with EyePart.
                // Arm descendants still animate; ancestors cannot move the visible eye.
                for (String name : G1BirkinEntity.EXPOSURE_BONES) {
                    var bone = getAnimationProcessor().getBone(name);
                    if (bone == null) continue;
                    bone.setRotX(0);
                    bone.setRotY(0);
                    bone.setRotZ(0);
                    bone.setPosX(0);
                    bone.setPosY(0);
                    bone.setPosZ(0);
                    bone.setScaleX(1);
                    bone.setScaleY(1);
                    bone.setScaleZ(1);
                }
            }
        }
        if (entity instanceof LickerEntity licker) {
            var root = getAnimationProcessor().getBone("root");
            if (root != null && licker.isHanging()) {
                root.setRotZ((float) Math.PI);
                root.setPosY(licker.getBbHeight() * 16);
            }
        }
    }

    private void hide(String name, boolean hidden) {
        var bone = getAnimationProcessor().getBone(name);
        if (bone != null) {
            bone.setHidden(hidden);
            // Approved parts are descendants of the animated phase wrapper.
            bone.setChildrenHidden(hidden);
        }
    }
}
