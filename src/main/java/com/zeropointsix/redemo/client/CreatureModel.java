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
        if (bone != null) bone.setHidden(hidden);
    }
}
