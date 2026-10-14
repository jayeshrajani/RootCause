"use client";

import type { ReactNode } from "react";
import { useFormContext, useWatch } from "react-hook-form";

import { BracketButton } from "@/components/brand/logo";
import { Stagger, StaggerItem } from "@/components/motion/reveal";
import { CROP_LABELS, SYMPTOM_DURATION_LABELS } from "@/lib/constants";
import { objectUrlFor } from "@/lib/object-urls";
import type { ReportFormInput } from "@/lib/schemas/report";

function Row({ label, onEdit, children }: { label: string; onEdit: () => void; children: ReactNode }) {
  return (
    <StaggerItem className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 py-5 sm:grid-cols-[8rem_1fr_auto]">
      <p className="label-caps pt-0.5 text-forest-600">{label}</p>
      <div className="col-span-2 row-start-2 min-w-0 sm:col-span-1 sm:row-start-1 sm:col-start-2">
        {children}
      </div>
      <BracketButton onClick={onEdit} className="-my-2 self-start text-forest-700 sm:col-start-3">
        Edit
      </BracketButton>
    </StaggerItem>
  );
}

export function ReviewStep({ goTo }: { goTo: (step: number) => void }) {
  const { control } = useFormContext<ReportFormInput>();
  const values = useWatch({ control });
  const images = values.images ?? [];

  return (
    <Stagger className="divide-y divide-forest-900/10 border-y border-forest-900/10">
      <Row label="Crop" onEdit={() => goTo(0)}>
        <p className="text-lg font-medium">{values.crop ? CROP_LABELS[values.crop] : "Not chosen"}</p>
      </Row>
      <Row label="Photos" onEdit={() => goTo(1)}>
        <div className="flex gap-2">
          {images.map((file, i) => (
            // eslint-disable-next-line @next/next/no-img-element -- local blob preview
            <img
              key={objectUrlFor(file)}
              src={objectUrlFor(file)}
              alt={`Photo ${i + 1}`}
              className="size-16 rounded-xl object-cover"
            />
          ))}
        </div>
      </Row>
      <Row label="Symptoms" onEdit={() => goTo(2)}>
        <p className="line-clamp-4 leading-relaxed">{values.description}</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Duration:{" "}
          {values.symptom_duration ? SYMPTOM_DURATION_LABELS[values.symptom_duration] : "not specified"}
        </p>
      </Row>
      <Row label="Location" onEdit={() => goTo(3)}>
        <p className="font-mono text-sm">
          {values.latitude}, {values.longitude}
        </p>
        {values.location_label ? (
          <p className="text-sm text-muted-foreground">{values.location_label}</p>
        ) : null}
      </Row>
    </Stagger>
  );
}
