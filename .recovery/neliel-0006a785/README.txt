Neliel body study 02 - exact Git commit recovery
Original commit: 0006a785bf2bdbc9e4a2f25f0dfbd67e63e34678
Parent commit:   3880db81a0b63e98e243dce334e0cddb1044b9b9
Bundle SHA256:   07e29513cf9d2bb094075769b0561593394405a39bab228882c7b4252184c1fe
The .b64 files are ordered chunks of a Git bundle containing ONLY the objects introduced by the original commit.
Reassembly: cat part-*.b64 | base64 -d > neliel-body-study-02.bundle
The workflow verifies both the bundle and target branch before pushing. It never force-pushes.
