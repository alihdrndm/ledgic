import { redirect } from "next/navigation";

/** /o/[org] → Pipeline (default screen). */
export default async function OrgIndex({ params }: { params: Promise<{ org: string }> }) {
  const { org } = await params;
  redirect(`/o/${org}/pipeline`);
}
